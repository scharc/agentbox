// Terminal management with xterm.js and WebSocket

// Mobile keyboard handling utilities
const MobileKeyboard = {
    resizeTimeout: null,
    resizeDebounceMs: 150,

    // Debounced resize handler - keyboard animation causes multiple resize events
    handleResize: function(callback) {
        if (this.resizeTimeout) {
            clearTimeout(this.resizeTimeout);
        }
        this.resizeTimeout = setTimeout(callback, this.resizeDebounceMs);
    },

    // Setup VisualViewport API (fallback for older browsers, supplement for others)
    setupVisualViewport: function(onResize) {
        if (window.visualViewport) {
            let pendingUpdate = false;
            const update = () => {
                pendingUpdate = false;
                onResize();
            };

            window.visualViewport.addEventListener('resize', () => {
                if (!pendingUpdate) {
                    pendingUpdate = true;
                    requestAnimationFrame(update);
                }
            });

            window.visualViewport.addEventListener('scroll', () => {
                if (!pendingUpdate) {
                    pendingUpdate = true;
                    requestAnimationFrame(update);
                }
            });

            console.log('VisualViewport API enabled');
        } else {
            console.log('VisualViewport API not available - relying on interactive-widget');
        }
    },

    // Debug panel disabled - no-op function
    showDebugInfo: function(message, data = null, append = false) {
        // Debug output disabled
    },

    // Adjust terminal height based on actual visible viewport
    adjustTerminalForKeyboard: function(term, fitAddon) {
        if (!window.visualViewport) {
            this.showDebugInfo('❌ No VisualViewport API');
            return;
        }

        const viewport = window.visualViewport;
        const termContainer = document.getElementById('terminal-container');
        const header = document.querySelector('.terminal-header');
        const keybar = document.querySelector('.keybar');

        if (!termContainer || !header || !keybar) {
            this.showDebugInfo('❌ Missing elements');
            return;
        }

        // Calculate available height
        const availableHeight = viewport.height - header.offsetHeight - keybar.offsetHeight;

        // Update container height dynamically - must clear conflicting CSS first
        termContainer.style.bottom = 'auto'; // Clear bottom positioning
        termContainer.style.top = `${header.offsetHeight}px`; // Set explicit top
        termContainer.style.height = `${availableHeight}px`; // Set explicit height

        // Force layout recalculation before fit
        termContainer.offsetHeight; // Trigger reflow

        // Verify the actual computed height
        const computedHeight = termContainer.offsetHeight;

        const debugData = {
            viewportHeight: viewport.height,
            windowHeight: window.innerHeight,
            headerHeight: header.offsetHeight,
            keybarHeight: keybar.offsetHeight,
            availableHeight: availableHeight,
            containerStyleHeight: termContainer.style.height,
            containerActualHeight: computedHeight,
            keyboardOpen: viewport.height < window.innerHeight
        };

        // Get actual positioning
        const containerRect = termContainer.getBoundingClientRect();

        this.showDebugInfo(
            `✅ Adjusted<br>VP: ${viewport.height}px<br>Calc: ${availableHeight}px<br>Set: ${termContainer.style.height}<br>Actual: ${computedHeight}px<br>Top: ${Math.round(containerRect.top)}px<br>Bottom: ${Math.round(containerRect.bottom)}px`,
            {
                ...debugData,
                containerTop: containerRect.top,
                containerBottom: containerRect.bottom,
                containerVisibleHeight: containerRect.bottom - containerRect.top
            }
        );
        console.log(`Terminal adjusted: viewport=${viewport.height}px, available=${availableHeight}px`);

        // Always fit terminal to match container size
        setTimeout(() => {
            try {
                const beforeFit = { cols: term.cols, rows: term.rows };

                // Detect if keyboard is open using viewport height threshold
                // Mobile keyboards typically reduce viewport from ~800-900px to ~500-600px
                // Use 700px as threshold: below = keyboard open, above = keyboard closed
                const keyboardOpen = viewport.height < 700;

                // Always fit terminal to container (whether keyboard open or closed)
                fitAddon.fit();

                const afterFit = { cols: term.cols, rows: term.rows };

            // Scroll to show cursor with context
            const baseRow = term.buffer.active.baseY;
            const cursorRow = term.buffer.active.cursorY;
            const viewportHeight = term.rows;

            // Get xterm viewport DOM element
            const xtermViewport = document.querySelector('.xterm-viewport');
            let targetScrollLine = 'none';

            // Calculate cursor's absolute position in the buffer
            const cursorAbsoluteRow = baseRow + cursorRow;

            // Let user control scrolling - no auto-scroll
            targetScrollLine = keyboardOpen ? 'manual-kb-open' : 'manual-kb-closed';

            const viewportScrollTop = xtermViewport ? xtermViewport.scrollTop : 0;
            const viewportScrollHeight = xtermViewport ? xtermViewport.scrollHeight : 0;
            const refitHappened = (beforeFit.rows !== afterFit.rows);

            const computedTargetLine = targetScrollLine.startsWith('line-')
                ? parseInt(targetScrollLine.split('-')[1])
                : -1;

            this.showDebugInfo(
                `🔧 ${keyboardOpen ? 'KB OPEN' : 'KB CLOSED'}<br>Term: ${afterFit.cols}x${afterFit.rows}<br>Cursor: rel ${cursorRow}, abs ${cursorAbsoluteRow}<br>Base: ${baseRow}<br>Target: ${targetScrollLine}<br>Scroll: ${Math.round(viewportScrollTop)}/${viewportScrollHeight}`,
                { beforeFit, afterFit, cursorRow, cursorAbsoluteRow, baseRow, computedTargetLine, keyboardOpen, refitHappened, targetScrollLine, viewportScrollTop, viewportScrollHeight, viewportHeightPx: viewport.height },
                true // append to previous debug info
            );

            } catch (error) {
                this.showDebugInfo(`❌ Error: ${error.message}`, { error: error.toString() }, true);
                console.error('adjustTerminalForKeyboard error:', error);
            }
        }, 100);
    },

    // Setup VirtualKeyboard API (Chrome Android only)
    setupVirtualKeyboard: function() {
        if ('virtualKeyboard' in navigator) {
            // Chrome Android: Take control of keyboard layout
            navigator.virtualKeyboard.overlaysContent = true;

            navigator.virtualKeyboard.addEventListener('geometrychange', () => {
                const { height } = navigator.virtualKeyboard.boundingRect;
                document.documentElement.style.setProperty('--keyboard-height', `${height}px`);
                console.log('VirtualKeyboard height:', height);
            });

            console.log('VirtualKeyboard API enabled (Chrome)');
        }
    },

    // Disable predictive text on xterm helper textarea
    disablePredictiveText: function() {
        setTimeout(() => {
            const textarea = document.querySelector('.xterm-helper-textarea');
            if (textarea) {
                textarea.setAttribute('autocomplete', 'off');
                textarea.setAttribute('autocorrect', 'off');
                textarea.setAttribute('autocapitalize', 'off');
                textarea.setAttribute('spellcheck', 'false');
                textarea.setAttribute('inputmode', 'text');
                console.log('Predictive text disabled on xterm textarea');
            }
        }, 100);
    }
};

// Get container and session from URL
const pathParts = window.location.pathname.split('/');
const container = decodeURIComponent(pathParts[2]);
const sessionName = decodeURIComponent(pathParts[3]);

// Update header with session info
document.getElementById('session-info').textContent = `${container} / ${sessionName}`;

// Initialize xterm.js
// Detect mobile for font size adjustment
const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)
    || window.innerWidth < 768;

const term = new Terminal({
    cursorBlink: true,
    fontSize: isMobile ? 11 : 14,  // Smaller font on mobile to fit more columns
    fontFamily: 'Menlo, Monaco, "Courier New", monospace',
    theme: {
        background: '#000000',
        foreground: '#ffffff',
        cursor: '#ffffff',
        selection: '#444444'
    },
    scrollback: 10000,
    allowProposedApi: true,
    windowOptions: {
        setWinLines: false  // Prevent window resize from clearing scrollback
    }
});

// Fit addon for responsive sizing
const fitAddon = new FitAddon.FitAddon();
term.loadAddon(fitAddon);

// Open terminal in container
const terminalContainer = document.getElementById('terminal-container');
term.open(terminalContainer);

// Ensure xterm viewport is always scrollable (mobile and desktop)
const xtermViewport = terminalContainer.querySelector('.xterm-viewport');
if (xtermViewport) {
    // Force scrollable viewport
    xtermViewport.style.overflowY = 'scroll';
    xtermViewport.style.overflowX = 'hidden';
    xtermViewport.style.webkitOverflowScrolling = 'touch';
    xtermViewport.style.touchAction = 'pan-y';  // Allow vertical scrolling

    console.log('Scrolling enabled on xterm-viewport (mobile and desktop)');
}

// Initial adjustment for mobile (before first fit)
MobileKeyboard.adjustTerminalForKeyboard(term, fitAddon);

// Fit terminal to container
fitAddon.fit();

// WebSocket connection with exponential backoff
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const wsUrl = `${protocol}//${window.location.host}/ws/${encodeURIComponent(container)}/${encodeURIComponent(sessionName)}`;
let ws = null;
let reconnectTimer = null;
let reconnectAttempts = 0;
let heartbeatInterval = null;
const MAX_RECONNECT_DELAY = 30000; // 30 seconds max
const BASE_RECONNECT_DELAY = 1000; // Start with 1 second
const HEARTBEAT_INTERVAL_MS = 10000; // Send heartbeat every 10 seconds

function getReconnectDelay() {
    // Exponential backoff with jitter
    const delay = Math.min(
        BASE_RECONNECT_DELAY * Math.pow(2, reconnectAttempts),
        MAX_RECONNECT_DELAY
    );
    return delay + Math.random() * 1000; // Add jitter
}

function connectWebSocket() {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log('WebSocket connected');
        reconnectAttempts = 0; // Reset on successful connection

        // Initialize controls panel with WebSocket
        if (window.TerminalControls) {
            window.TerminalControls.init(ws);
        }

        // Start heartbeat to keep connection alive
        if (heartbeatInterval) {
            clearInterval(heartbeatInterval);
        }
        heartbeatInterval = setInterval(() => {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send('__PING__');
            }
        }, HEARTBEAT_INTERVAL_MS);
        console.log('Started heartbeat');

        // Log connection but don't send resize yet - wait for __INIT__
        const { cols, rows } = term;
        MobileKeyboard.showDebugInfo(
            `🔌 WS OPEN<br>Terminal: ${cols}x${rows}<br>Waiting for __INIT__`,
            { cols, rows },
            true
        );
    };

    ws.onmessage = (event) => {
        const data = event.data;

        // Handle initialization message with tmux dimensions
        if (data.startsWith('__INIT__')) {
            try {
                const dimensions = data.substring(8); // Remove "__INIT__"
                const [tmuxWidth, tmuxHeight] = dimensions.split('x').map(Number);
                const { cols, rows } = term;

                console.log(`Tmux session: ${tmuxWidth}x${tmuxHeight}, Terminal: ${cols}x${rows}`);

                const needsResize = tmuxWidth !== cols || tmuxHeight !== rows;

                MobileKeyboard.showDebugInfo(
                    `📡 INIT<br>Tmux: ${tmuxWidth}x${tmuxHeight}<br>Term: ${cols}x${rows}<br>Resize: ${needsResize ? 'YES' : 'NO'}`,
                    { tmuxWidth, tmuxHeight, termCols: cols, termRows: rows, needsResize },
                    true
                );

                // If dimensions don't match, resize tmux to match our terminal
                if (needsResize) {
                    console.log(`Resizing tmux session to match terminal: ${cols}x${rows}`);
                    ws.send(`__RESIZE__${cols}x${rows}`);
                    MobileKeyboard.showDebugInfo(
                        `📏 SENT RESIZE<br>${cols}x${rows}`,
                        { cols, rows },
                        true
                    );
                    // Wait for resize and tmux redraw to complete, then signal ready
                    setTimeout(() => {
                        ws.send('__READY__');
                        MobileKeyboard.showDebugInfo('✅ SENT READY', {}, true);
                    }, 1000);  // Wait 1000ms for resize and tmux redraw to complete
                } else {
                    // Dimensions match, signal ready immediately
                    ws.send('__READY__');
                    MobileKeyboard.showDebugInfo('✅ SENT READY (no resize)', {}, true);
                }
            } catch (e) {
                console.error('Failed to parse init dimensions:', e);
                // Signal ready anyway
                ws.send('__READY__');
            }
            return;
        }

        // v32-AUTOSCROLL: Polling with auto-scroll to cursor
        // Server sends: \x1b[2J\x1b[H + positioned lines + cursor position
        // Client auto-scrolls to keep cursor visible when keyboard open
        term.write(data);
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        term.write('\r\n[Connection error]\r\n');
    };

    ws.onclose = () => {
        console.log('WebSocket closed');

        // Stop heartbeat
        if (heartbeatInterval) {
            clearInterval(heartbeatInterval);
            heartbeatInterval = null;
            console.log('Stopped heartbeat');
        }

        reconnectAttempts++;
        const delay = getReconnectDelay();
        term.write(`\r\n[Disconnected. Reconnecting in ${Math.round(delay/1000)}s...]\r\n`);

        // Attempt to reconnect with exponential backoff
        reconnectTimer = setTimeout(() => {
            connectWebSocket();
        }, delay);
    };
}

// Handle terminal input
term.onData((data) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(data);
    }

    // Keep cursor visible when typing (mobile keyboard open)
    if (window.visualViewport) {
        const baseRow = term.buffer.active.baseY;
        const cursorRow = term.buffer.active.cursorY;
        const cursorAbsoluteRow = baseRow + cursorRow;
        const xtermViewport = document.querySelector('.xterm-viewport');
        const scrollTop = xtermViewport ? xtermViewport.scrollTop : 0;
        const scrollHeight = xtermViewport ? xtermViewport.scrollHeight : 0;
        const keyboardOpen = window.visualViewport.height < 700;

        // No auto-scroll on input - user controls scrolling

        MobileKeyboard.showDebugInfo(
            `⌨️ INPUT<br>KB: ${keyboardOpen ? 'OPEN' : 'CLOSED'}<br>Cursor: abs ${cursorAbsoluteRow}<br>Scroll: ${Math.round(scrollTop)}/${scrollHeight}`,
            {
                input: data.charCodeAt(0),
                cursorAbsoluteRow,
                baseRow,
                cursorRow,
                scrollTop,
                scrollHeight,
                keyboardOpen,
                viewportHeight: window.visualViewport.height
            },
            true
        );
    }
});

// Handle terminal resize
function handleResize() {
    // Capture dimensions BEFORE any changes
    const beforeCols = term.cols;
    const beforeRows = term.rows;

    console.log(`[RESIZE] Before: ${beforeCols}x${beforeRows}`);

    // Adjust for mobile keyboard and fit
    MobileKeyboard.adjustTerminalForKeyboard(term, fitAddon);

    // Check dimensions AFTER
    const afterCols = term.cols;
    const afterRows = term.rows;

    const changed = beforeCols !== afterCols || beforeRows !== afterRows;
    const wsReady = ws && ws.readyState === WebSocket.OPEN;

    console.log(`[RESIZE] After: ${afterCols}x${afterRows}, changed: ${changed}`);

    // Mobile debug logging
    MobileKeyboard.showDebugInfo(
        `📐 RESIZE<br>Before: ${beforeCols}x${beforeRows}<br>After: ${afterCols}x${afterRows}<br>WS: ${wsReady ? 'READY' : 'NOT READY'}`,
        {
            beforeCols,
            beforeRows,
            afterCols,
            afterRows,
            changed,
            wsReady,
            wsState: ws ? ws.readyState : null
        },
        true
    );

    // Send resize to backend if dimensions changed
    if (wsReady && changed) {
        console.log(`[RESIZE] Sending to backend: ${afterCols}x${afterRows}`);
        ws.send(`__RESIZE__${afterCols}x${afterRows}`);
        MobileKeyboard.showDebugInfo(
            `✅ RESIZE SENT<br>${afterCols}x${afterRows}`,
            { cols: afterCols, rows: afterRows },
            true
        );
    } else if (!wsReady) {
        console.log(`[RESIZE] WebSocket not ready, state: ${ws ? ws.readyState : 'null'}`);
    } else if (!changed) {
        console.log(`[RESIZE] No change in dimensions`);
    }
}

// Debounced resize handler for mobile keyboard animations
function debouncedResize() {
    MobileKeyboard.handleResize(handleResize);
}

// Resize on window resize (fires when keyboard appears with interactive-widget=resizes-content)
window.addEventListener('resize', debouncedResize);

// Resize on orientation change (mobile)
window.addEventListener('orientationchange', () => {
    MobileKeyboard.handleResize(handleResize);
});

// Setup mobile keyboard APIs
MobileKeyboard.setupVirtualKeyboard();
MobileKeyboard.setupVisualViewport(handleResize);
MobileKeyboard.disablePredictiveText();

// Track manual scroll events
// Note: xtermViewport already declared above, reusing it here
if (xtermViewport) {
    let scrollDebounce = null;
    xtermViewport.addEventListener('scroll', () => {
        if (scrollDebounce) {
            clearTimeout(scrollDebounce);
        }
        scrollDebounce = setTimeout(() => {
            const baseRow = term.buffer.active.baseY;
            const cursorRow = term.buffer.active.cursorY;
            const cursorAbsoluteRow = baseRow + cursorRow;
            const scrollTop = xtermViewport.scrollTop;
            const scrollHeight = xtermViewport.scrollHeight;
            const keyboardOpen = window.visualViewport && window.visualViewport.height < 700;

            MobileKeyboard.showDebugInfo(
                `📜 SCROLL<br>KB: ${keyboardOpen ? 'OPEN' : 'CLOSED'}<br>Cursor: abs ${cursorAbsoluteRow}<br>Scroll: ${Math.round(scrollTop)}/${scrollHeight}`,
                {
                    cursorAbsoluteRow,
                    baseRow,
                    cursorRow,
                    scrollTop,
                    scrollHeight,
                    keyboardOpen,
                    viewportHeight: window.visualViewport ? window.visualViewport.height : 0
                },
                true
            );
        }, 200);
    });
}

// Show initial debug info
if (window.visualViewport) {
    MobileKeyboard.showDebugInfo(`📱 Initial load<br>VP: ${window.visualViewport.height}px<br>Window: ${window.innerHeight}px`);
} else {
    MobileKeyboard.showDebugInfo('⚠️ No VisualViewport API<br>Browser: ' + navigator.userAgent.split(' ').pop());
}

// Initial connection
connectWebSocket();

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (reconnectTimer) {
        clearTimeout(reconnectTimer);
    }
    if (heartbeatInterval) {
        clearInterval(heartbeatInterval);
    }
    if (ws) {
        ws.close();
    }
});

// Focus terminal on load
term.focus();

// Export terminal instance for keybar.js
window.agentboxTerminal = term;
window.agentboxWebSocket = () => ws;

// Font size controls
const MIN_FONT_SIZE = 10;
const MAX_FONT_SIZE = 24;
const FONT_SIZE_KEY = 'agentbox_fontSize';

function updateFontSize(newSize) {
    const size = Math.max(MIN_FONT_SIZE, Math.min(MAX_FONT_SIZE, newSize));
    term.options.fontSize = size;
    fitAddon.fit();
    document.getElementById('font-size-display').textContent = size;
    localStorage.setItem(FONT_SIZE_KEY, size);

    // Notify tmux of new dimensions
    if (ws && ws.readyState === WebSocket.OPEN) {
        const { cols, rows } = term;
        ws.send(`__RESIZE__${cols}x${rows}`);
    }
}

// Font size button handlers
document.getElementById('font-increase')?.addEventListener('click', () => {
    updateFontSize(term.options.fontSize + 1);
});

document.getElementById('font-decrease')?.addEventListener('click', () => {
    updateFontSize(term.options.fontSize - 1);
});

// Restore saved font size
const savedFontSize = localStorage.getItem(FONT_SIZE_KEY);
if (savedFontSize) {
    const size = parseInt(savedFontSize, 10);
    if (size >= MIN_FONT_SIZE && size <= MAX_FONT_SIZE) {
        term.options.fontSize = size;
        document.getElementById('font-size-display').textContent = size;
        fitAddon.fit();
    }
}

// Copy/paste functionality
document.getElementById('copy-btn')?.addEventListener('click', async () => {
    const selection = term.getSelection();
    if (selection) {
        try {
            await navigator.clipboard.writeText(selection);
            // Visual feedback
            const btn = document.getElementById('copy-btn');
            const originalText = btn.textContent;
            btn.textContent = 'Copied!';
            setTimeout(() => { btn.textContent = originalText; }, 1000);
        } catch (err) {
            console.error('Failed to copy:', err);
        }
    }
    term.focus();
});

document.getElementById('paste-btn')?.addEventListener('click', async () => {
    try {
        const text = await navigator.clipboard.readText();
        if (text && ws && ws.readyState === WebSocket.OPEN) {
            ws.send(text);
        }
    } catch (err) {
        console.error('Failed to paste:', err);
    }
    term.focus();
});
