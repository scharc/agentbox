// Status page management for boxctl Web UI

const statusContainer = document.getElementById('status-container');
const refreshBtn = document.getElementById('refresh-btn');
const confirmModal = document.getElementById('confirm-modal');
const confirmTitle = document.getElementById('confirm-title');
const confirmMessage = document.getElementById('confirm-message');
const confirmBtn = document.querySelector('.confirm-btn');
const cancelBtn = confirmModal.querySelector('.cancel-btn');
const closeModalBtn = confirmModal.querySelector('.close-modal');

// Auto-refresh interval (5 seconds)
const REFRESH_INTERVAL = 5000;
let refreshTimer = null;
let pendingAction = null;

// Fetch status from API
async function fetchStatus() {
    try {
        const response = await fetch('/api/status');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Failed to fetch status:', error);
        return null;
    }
}

// Format bytes to human readable
function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Render status UI
function renderStatus(data) {
    if (!data) {
        statusContainer.innerHTML = `
            <div class="status-error">
                <div class="error-icon">&#9888;</div>
                <p>Failed to load status</p>
                <button class="btn-primary" onclick="loadStatus()">Retry</button>
            </div>
        `;
        return;
    }

    let html = '';

    // Service Status Section
    const serviceStatus = data.service?.status || 'unknown';
    const statusClass = serviceStatus === 'running' ? 'status-ok' : 'status-error';
    const statusIcon = serviceStatus === 'running' ? '&#10004;' : '&#10008;';

    html += `
        <section class="status-section">
            <div class="section-header">
                <h2>Service</h2>
            </div>
            <div class="status-card service-card">
                <div class="status-row">
                    <span class="status-label">boxctld</span>
                    <span class="status-indicator ${statusClass}">${statusIcon} ${escapeHtml(serviceStatus)}</span>
                </div>
                <div class="status-row">
                    <span class="status-label">Connected</span>
                    <span class="status-value">${data.service?.connected_containers?.length || 0} containers</span>
                </div>
                <div class="action-row">
                    <button class="action-btn btn-warning" onclick="confirmAction('restart-service', 'Restart Service', 'This will restart the boxctld service. Active connections may be briefly interrupted.')">
                        &#8635; Restart Service
                    </button>
                </div>
            </div>
        </section>
    `;

    // SSH Tunnels Section
    const sshTunnel = data.tunnels?.ssh_tunnel || {};
    const connectedCount = sshTunnel.connected_containers || 0;
    const totalForwards = sshTunnel.total_forwards || 0;

    html += `
        <section class="status-section">
            <div class="section-header">
                <h2>SSH Tunnel</h2>
            </div>
            <div class="status-card tunnel-card">
                <div class="status-row">
                    <span class="status-label">Connected Containers</span>
                    <span class="status-value ${connectedCount > 0 ? 'count-ok' : 'count-zero'}">${connectedCount}</span>
                </div>
                <div class="status-row">
                    <span class="status-label">Port Forwards</span>
                    <span class="status-value">${totalForwards}</span>
                </div>
            </div>
        </section>
    `;

    // Containers Section
    const containers = data.containers || [];

    html += `
        <section class="status-section">
            <div class="section-header">
                <h2>Containers</h2>
            </div>
    `;

    if (containers.length === 0) {
        html += '<div class="status-card"><div class="tunnel-empty">No containers found</div></div>';
    } else {
        for (const container of containers) {
            const isRunning = container.status === 'running';
            const statusClass = isRunning ? 'status-ok' : 'status-stopped';
            const statusIcon = isRunning ? '&#9679;' : '&#9675;';
            const tunnelStatus = container.tunnel_connected ? 'Tunnel OK' : 'No tunnel';
            const tunnelClass = container.tunnel_connected ? 'tunnel-ok' : 'tunnel-none';

            html += `
                <div class="status-card container-card">
                    <div class="container-header">
                        <span class="container-name">${escapeHtml(container.project || container.name)}</span>
                        <span class="container-status ${statusClass}">${statusIcon} ${escapeHtml(container.status)}</span>
                    </div>
                    <div class="container-details">
                        <span class="container-fullname">${escapeHtml(container.name)}</span>
                        <span class="container-tunnel ${tunnelClass}">${tunnelStatus}</span>
                    </div>
                    <div class="action-row">
            `;

            if (isRunning) {
                html += `
                    <button class="action-btn btn-warning" onclick="confirmAction('restart-container', 'Restart Container', 'Restart ${escapeHtml(container.name)}?', '${escapeHtml(container.name)}')">
                        &#8635; Restart
                    </button>
                    <button class="action-btn btn-danger" onclick="confirmAction('stop-container', 'Stop Container', 'Stop ${escapeHtml(container.name)}? Running sessions will be terminated.', '${escapeHtml(container.name)}')">
                        &#9632; Stop
                    </button>
                    <button class="action-btn btn-rebase" onclick="confirmAction('rebase-container', 'Rebase Container', 'Rebase ${escapeHtml(container.name)} to latest base image? This will recreate the container and terminate all sessions.', '${escapeHtml(container.name)}')">
                        &#8593; Rebase
                    </button>
                `;
            } else {
                html += `
                    <button class="action-btn btn-success" onclick="confirmAction('start-container', 'Start Container', 'Start ${escapeHtml(container.name)}?', '${escapeHtml(container.name)}')">
                        &#9654; Start
                    </button>
                    <button class="action-btn btn-rebase" onclick="confirmAction('rebase-container', 'Rebase Container', 'Rebase ${escapeHtml(container.name)} to latest base image? This will recreate the container.', '${escapeHtml(container.name)}')">
                        &#8593; Rebase
                    </button>
                `;
            }

            html += '</div></div>';
        }
    }

    html += '</section>';

    statusContainer.innerHTML = html;
}

// Show confirmation modal
function confirmAction(action, title, message, target = null) {
    pendingAction = { action, target };
    confirmTitle.textContent = title;
    confirmMessage.textContent = message;
    confirmModal.classList.add('show');

    // Update button style based on action
    confirmBtn.className = 'btn-danger confirm-btn';
    if (action === 'start-container') {
        confirmBtn.className = 'btn-success confirm-btn';
    } else if (action === 'rebase-container') {
        confirmBtn.className = 'btn-rebase confirm-btn';
    }
}

// Hide confirmation modal
function hideModal() {
    confirmModal.classList.remove('show');
    pendingAction = null;
}

// Execute confirmed action
async function executeAction() {
    if (!pendingAction) return;

    const { action, target } = pendingAction;
    hideModal();

    // Show loading state
    const btn = event.target;
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = action === 'rebase-container' ? 'Rebasing...' : 'Working...';

    let url;
    switch (action) {
        case 'restart-service':
            url = '/api/service/restart';
            break;
        case 'restart-container':
            url = `/api/container/${encodeURIComponent(target)}/restart`;
            break;
        case 'stop-container':
            url = `/api/container/${encodeURIComponent(target)}/stop`;
            break;
        case 'start-container':
            url = `/api/container/${encodeURIComponent(target)}/start`;
            break;
        case 'rebase-container':
            url = `/api/container/${encodeURIComponent(target)}/rebase`;
            break;
        default:
            console.error('Unknown action:', action);
            return;
    }

    try {
        const response = await fetch(url, { method: 'POST' });
        const result = await response.json();

        if (!result.ok && !response.ok) {
            alert(`Action failed: ${result.error || result.detail || 'Unknown error'}`);
        }

        // Refresh status after action
        setTimeout(loadStatus, 1000);
    } catch (error) {
        console.error('Action failed:', error);
        alert(`Action failed: ${error.message}`);
    } finally {
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

// Load and render status
async function loadStatus() {
    const data = await fetchStatus();
    renderStatus(data);
}

// Start auto-refresh
function startAutoRefresh() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
    }
    refreshTimer = setInterval(loadStatus, REFRESH_INTERVAL);
}

// Stop auto-refresh
function stopAutoRefresh() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
    }
}

// Event listeners
refreshBtn.addEventListener('click', async () => {
    refreshBtn.innerHTML = '&#8987; Refreshing...';
    await loadStatus();
    refreshBtn.innerHTML = '&#128260; Refresh';
});

confirmBtn.addEventListener('click', executeAction);
cancelBtn.addEventListener('click', hideModal);
closeModalBtn.addEventListener('click', hideModal);

confirmModal.addEventListener('click', (e) => {
    if (e.target === confirmModal) {
        hideModal();
    }
});

// Keyboard: Escape closes modal
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && confirmModal.classList.contains('show')) {
        hideModal();
    }
});

// Stop auto-refresh when page is hidden (save resources)
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        stopAutoRefresh();
    } else {
        startAutoRefresh();
        loadStatus();
    }
});

// Initial load
loadStatus();
startAutoRefresh();
