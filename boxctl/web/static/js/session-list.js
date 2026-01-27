// Session list management for boxctl Web UI

const sessionsContainer = document.getElementById('sessions-container');
const refreshBtn = document.getElementById('refresh-btn');
const newSessionBtn = document.getElementById('new-session-btn');
const newSessionModal = document.getElementById('new-session-modal');
const newSessionForm = document.getElementById('new-session-form');
const containerSelect = document.getElementById('container-select');
const agentTypeSelect = document.getElementById('agent-type-select');
const identifierInput = document.getElementById('identifier-input');

// Auto-refresh interval (5 seconds)
const REFRESH_INTERVAL = 5000;
let refreshTimer = null;
let availableContainers = [];

// Fetch sessions from API
async function fetchSessions() {
    try {
        const response = await fetch('/api/sessions');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        return data.sessions || [];
    } catch (error) {
        console.error('Failed to fetch sessions:', error);
        return [];
    }
}

// Render sessions as cards
function renderSessions(sessions) {
    if (sessions.length === 0) {
        sessionsContainer.innerHTML = '<div class="loading">No active sessions found</div>';
        return;
    }

    // Extract unique containers
    const containers = [...new Set(sessions.map(s => s.container))];
    availableContainers = containers;
    updateContainerSelect();

    // Group sessions by container
    const grouped = sessions.reduce((acc, session) => {
        if (!acc[session.container]) {
            acc[session.container] = [];
        }
        acc[session.container].push(session);
        return acc;
    }, {});

    let html = '';

    sessions.forEach(session => {
        const statusClass = session.attached ? 'attached' : 'detached';
        const statusText = session.attached ? 'Attached' : 'Detached';

        html += `
            <div class="session-card" data-container="${escapeHtml(session.container)}"
                 data-session="${escapeHtml(session.name)}">
                <div>
                    <div class="session-header">
                        <span class="session-name">${escapeHtml(session.name)}</span>
                        <span class="session-status ${statusClass}">${statusText}</span>
                    </div>
                    <div class="session-container">
                        📦 ${escapeHtml(session.container)} • ${session.windows} window(s)
                    </div>
                </div>
            </div>
        `;
    });

    sessionsContainer.innerHTML = html;

    // Add click handlers
    document.querySelectorAll('.session-card').forEach(card => {
        card.addEventListener('click', () => {
            const container = card.dataset.container;
            const session = card.dataset.session;
            window.location.href = `/session/${encodeURIComponent(container)}/${encodeURIComponent(session)}`;
        });
    });
}

// Update container select options
function updateContainerSelect() {
    // Preserve current selection
    const currentValue = containerSelect.value;

    containerSelect.innerHTML = '<option value="">Select container...</option>';
    availableContainers.forEach(container => {
        const option = document.createElement('option');
        option.value = container;
        option.textContent = container;
        containerSelect.appendChild(option);
    });

    // Restore selection if it still exists
    if (currentValue && availableContainers.includes(currentValue)) {
        containerSelect.value = currentValue;
    }
}

// Track element that opened modal for focus restoration
let modalTriggerElement = null;

// Show modal
function showModal() {
    modalTriggerElement = document.activeElement;
    newSessionModal.classList.add('show');
    newSessionForm.reset();
    // Focus first focusable element in modal
    setTimeout(() => {
        containerSelect.focus();
    }, 100);
}

// Hide modal
function hideModal() {
    newSessionModal.classList.remove('show');
    // Restore focus to trigger element
    if (modalTriggerElement) {
        modalTriggerElement.focus();
        modalTriggerElement = null;
    }
}

// Keyboard navigation for modal
document.addEventListener('keydown', (e) => {
    // Escape key closes modal
    if (e.key === 'Escape' && newSessionModal.classList.contains('show')) {
        hideModal();
        return;
    }

    // Focus trap in modal
    if (e.key === 'Tab' && newSessionModal.classList.contains('show')) {
        const focusableElements = newSessionModal.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        const firstElement = focusableElements[0];
        const lastElement = focusableElements[focusableElements.length - 1];

        if (e.shiftKey) {
            // Shift+Tab: go to last element if at first
            if (document.activeElement === firstElement) {
                e.preventDefault();
                lastElement.focus();
            }
        } else {
            // Tab: go to first element if at last
            if (document.activeElement === lastElement) {
                e.preventDefault();
                firstElement.focus();
            }
        }
    }
});

// Create new session
async function createSession(container, agentType, identifier) {
    try {
        const response = await fetch('/api/sessions', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                container,
                agent_type: agentType,
                identifier: identifier || null,
            }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to create session');
        }

        const result = await response.json();
        return result;
    } catch (error) {
        console.error('Failed to create session:', error);
        throw error;
    }
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Load and render sessions
async function loadSessions() {
    const sessions = await fetchSessions();
    renderSessions(sessions);
}

// Start auto-refresh
function startAutoRefresh() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
    }
    refreshTimer = setInterval(loadSessions, REFRESH_INTERVAL);
}

// Stop auto-refresh
function stopAutoRefresh() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
    }
}

// Manual refresh
refreshBtn.addEventListener('click', async () => {
    refreshBtn.innerHTML = '&#8987;';
    await loadSessions();
    refreshBtn.innerHTML = '&#128260;';
});

// New session button
newSessionBtn.addEventListener('click', () => {
    showModal();
});

// Close modal handlers
document.querySelector('.close-modal').addEventListener('click', hideModal);
document.querySelector('.cancel-btn').addEventListener('click', hideModal);

// Close modal when clicking outside
newSessionModal.addEventListener('click', (e) => {
    if (e.target === newSessionModal) {
        hideModal();
    }
});

// Handle form submission
newSessionForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const container = containerSelect.value;
    const agentType = agentTypeSelect.value;
    const identifier = identifierInput.value.trim();

    if (!container || !agentType) {
        alert('Please select a container and agent type');
        return;
    }

    try {
        // Disable form during submission
        const submitBtn = newSessionForm.querySelector('button[type="submit"]');
        submitBtn.disabled = true;
        submitBtn.textContent = 'Creating...';

        const result = await createSession(container, agentType, identifier);

        // Success - hide modal and refresh sessions
        hideModal();
        await loadSessions();

        // Navigate to the new session
        window.location.href = `/session/${encodeURIComponent(container)}/${encodeURIComponent(result.session_name)}`;
    } catch (error) {
        alert(`Failed to create session: ${error.message}`);
        // Re-enable form
        const submitBtn = newSessionForm.querySelector('button[type="submit"]');
        submitBtn.disabled = false;
        submitBtn.textContent = 'Create Session';
    }
});

// Stop auto-refresh when page is hidden (save resources)
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        stopAutoRefresh();
    } else {
        startAutoRefresh();
        loadSessions(); // Refresh immediately when page becomes visible
    }
});

// Initial load
loadSessions();
startAutoRefresh();
