// Mobile keybar for special keys
// Simplified: keybar buttons send directly, xterm.js handles regular keyboard input

const keybar = document.getElementById('keybar');
let ctrlActive = false;

// Special key mappings to ANSI escape sequences
const SPECIAL_KEYS = {
    'Escape': '\x1B',
    'Tab': '\t',
    'Enter': '\r',
    'ArrowUp': '\x1B[A',
    'ArrowDown': '\x1B[B',
    'ArrowLeft': '\x1B[D',
    'ArrowRight': '\x1B[C',
    'Backspace': '\x7F',
    'Delete': '\x1B[3~',
    'Home': '\x1B[H',
    'End': '\x1B[F',
    'PageUp': '\x1B[5~',
    'PageDown': '\x1B[6~',
};

// Ctrl key combinations
function withCtrl(char) {
    const code = char.toUpperCase().charCodeAt(0) - 64;
    return String.fromCharCode(code);
}

// Send key sequence via WebSocket
function sendKey(sequence) {
    const ws = window.agentboxWebSocket();
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(sequence);
    }
}

// Haptic feedback utility
function hapticFeedback(pattern = 20) {
    if (navigator.vibrate) {
        navigator.vibrate(pattern);
    }
}

// Handle key button press
function handleKeyPress(target) {
    if (!target.classList.contains('key-btn')) return;

    const key = target.dataset.key;

    // Haptic feedback
    hapticFeedback();

    // Visual feedback
    target.classList.add('active');
    setTimeout(() => target.classList.remove('active'), 150);

    // Handle special commands
    if (key === 'TmuxPrefix') {
        sendKey(withCtrl('a'));
        return;
    }

    if (key === 'Detach') {
        sendKey(withCtrl('a'));
        setTimeout(() => sendKey('d'), 50);
        return;
    }

    if (key === 'Control') {
        ctrlActive = !ctrlActive;
        target.classList.toggle('active', ctrlActive);
        target.setAttribute('aria-pressed', ctrlActive);
        // Double pulse for toggle feedback
        if (ctrlActive) hapticFeedback([50, 30, 50]);
        return;
    }

    // Handle special keys
    if (SPECIAL_KEYS[key]) {
        let sequence = SPECIAL_KEYS[key];

        // Apply Ctrl modifier if active
        if (ctrlActive && key === 'Enter') {
            sequence = withCtrl('m');
        }

        sendKey(sequence);

        // Reset Ctrl modifier after use
        if (ctrlActive) {
            ctrlActive = false;
            document.querySelector('[data-key="Control"]')?.classList.remove('active');
        }
    }

    // Focus terminal after button press (allows keyboard to appear on tap)
    if (window.agentboxTerminal) {
        window.agentboxTerminal.focus();
    }
}

// Handle keybar button touches (mobile) - use touchend for better response
keybar.addEventListener('touchend', (e) => {
    if (!e.target.classList.contains('key-btn')) return;
    e.preventDefault();
    handleKeyPress(e.target);
}, { passive: false });

// Handle keybar button clicks (desktop fallback)
keybar.addEventListener('click', (e) => {
    if (!e.target.classList.contains('key-btn')) return;
    handleKeyPress(e.target);
});

// Initial terminal focus
if (window.agentboxTerminal) {
    window.agentboxTerminal.focus();
}

console.log('Keybar initialized');
