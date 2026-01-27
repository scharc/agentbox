/**
 * Floating controls panel for terminal - scroll and key controls
 */

(function() {
    'use strict';

    let ws = null;
    let controlsVisible = false;

    function init(websocket) {
        ws = websocket;
        setupToggleButton();
        setupScrollButtons();
        setupKeyButtons();
    }

    function setupToggleButton() {
        const toggleBtn = document.getElementById('controls-toggle');
        const panel = document.getElementById('controls-panel');

        if (!toggleBtn || !panel) return;

        toggleBtn.addEventListener('click', () => {
            controlsVisible = !controlsVisible;
            if (controlsVisible) {
                panel.classList.remove('hidden');
            } else {
                panel.classList.add('hidden');
            }
        });

        // Close panel when clicking outside
        document.addEventListener('click', (e) => {
            if (controlsVisible &&
                !panel.contains(e.target) &&
                e.target !== toggleBtn) {
                controlsVisible = false;
                panel.classList.add('hidden');
            }
        });
    }

    function setupScrollButtons() {
        // Enter tmux copy mode and send scroll commands
        const scrollUpPage = document.getElementById('scroll-up-page');
        const scrollUp = document.getElementById('scroll-up');
        const scrollDown = document.getElementById('scroll-down');
        const scrollDownPage = document.getElementById('scroll-down-page');
        const scrollExit = document.getElementById('scroll-exit');

        if (scrollUpPage) {
            scrollUpPage.addEventListener('click', () => {
                // Ctrl+A [ (enter copy mode), then Page Up
                sendTmuxKeys('\x01[');
                setTimeout(() => sendKey('PageUp'), 100);
            });
        }

        if (scrollUp) {
            scrollUp.addEventListener('click', () => {
                // Ctrl+A [ (enter copy mode), then Up arrow
                sendTmuxKeys('\x01[');
                setTimeout(() => sendKey('ArrowUp'), 100);
            });
        }

        if (scrollDown) {
            scrollDown.addEventListener('click', () => {
                // In copy mode, send Down arrow
                sendKey('ArrowDown');
            });
        }

        if (scrollDownPage) {
            scrollDownPage.addEventListener('click', () => {
                // In copy mode, send Page Down
                sendKey('PageDown');
            });
        }

        if (scrollExit) {
            scrollExit.addEventListener('click', () => {
                // Exit copy mode with 'q'
                sendTmuxKeys('q');
            });
        }
    }

    function setupKeyButtons() {
        const keyButtons = document.querySelectorAll('#controls-panel .control-btn[data-key]');

        keyButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const key = btn.getAttribute('data-key');
                if (key === 'Control') {
                    btn.classList.toggle('active');
                } else {
                    sendKey(key);
                }
            });
        });
    }

    function sendKey(key) {
        // Convert key name to escape sequence or character
        const keyMap = {
            'Escape': '\x1B',
            'Tab': '\t',
            'ArrowUp': '\x1B[A',
            'ArrowDown': '\x1B[B',
            'ArrowLeft': '\x1B[D',
            'ArrowRight': '\x1B[C',
            'PageUp': '\x1B[5~',
            'PageDown': '\x1B[6~',
        };

        const data = keyMap[key] || key;
        sendTmuxKeys(data);
    }

    function sendTmuxKeys(data) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(data);
        }
    }

    // Export to global scope
    window.TerminalControls = {
        init: init
    };
})();
