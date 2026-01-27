---
name: remote-chrome
description: Connect to and control a remote Chrome browser via Chrome DevTools Protocol (CDP). Use when the user mentions "remote chrome", "chrome debugging", "CDP", "devtools protocol", "browser automation", "control chrome", or when tasks require interacting with a Chrome browser running on the host. The Chrome instance must be started with --remote-debugging-port=9222 on the host, and port 9222 must be forwarded into the container.
metadata:
  short-description: Control Chrome via DevTools Protocol
---

# Remote Chrome Usage

Control a Chrome browser running on the host via the Chrome DevTools Protocol (CDP).

## Prerequisites

### 1. Host Setup (User Must Do This)

Chrome must be started with remote debugging enabled on the host:

```bash
# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222

# Linux
google-chrome --remote-debugging-port=9222

# Windows
chrome.exe --remote-debugging-port=9222

# Headless mode (no visible window)
google-chrome --headless --remote-debugging-port=9222 --no-sandbox --remote-allow-origins=*
```

### 2. Port Forwarding (User Must Do This)

Forward port 9222 into the container:

```bash
# From host terminal (outside container)
boxctl ports forward 9222
```

Or add to `.boxctl.yml`:

```yaml
ports:
  container:
    - '9222'
```

## Verifying Connection

Always verify the connection before attempting automation:

```bash
# Check if CDP is reachable
curl -s http://localhost:9222/json/version

# List available targets (tabs/pages)
curl -s http://localhost:9222/json/list
```

Expected response from `/json/version`:
```json
{
  "Browser": "Chrome/XXX.X.X.X",
  "webSocketDebuggerUrl": "ws://localhost:9222/devtools/browser/UUID"
}
```

## Connection Methods

### Method 1: Node.js with chrome-remote-interface (Recommended)

```bash
# Install the package
npm install chrome-remote-interface
```

```javascript
const CDP = require('chrome-remote-interface');

async function main() {
    const client = await CDP({ port: 9222 });
    const { Page, Runtime, DOM } = client;

    // Enable required domains
    await Promise.all([Page.enable(), Runtime.enable(), DOM.enable()]);

    // Navigate to a URL
    await Page.navigate({ url: 'https://example.com' });
    await Page.loadEventFired();

    // Execute JavaScript in the page
    const result = await Runtime.evaluate({
        expression: 'document.title'
    });
    console.log('Page title:', result.result.value);

    // Get page HTML
    const { root } = await DOM.getDocument();
    const { outerHTML } = await DOM.getOuterHTML({ nodeId: root.nodeId });
    console.log('HTML length:', outerHTML.length);

    await client.close();
}

main().catch(console.error);
```

### Method 2: Python with pychrome

```bash
pip install pychrome
```

```python
import pychrome

# Connect to Chrome
browser = pychrome.Browser(url="http://localhost:9222")

# Get first tab or create new one
tabs = browser.list_tab()
if tabs:
    tab = tabs[0]
else:
    tab = browser.new_tab()

tab.start()

# Enable required domains
tab.Page.enable()
tab.Runtime.enable()
tab.DOM.enable()

# Navigate
tab.Page.navigate(url="https://example.com")
tab.wait(5)  # Wait for load

# Execute JavaScript
result = tab.Runtime.evaluate(expression="document.title")
print("Title:", result['result']['value'])

# Get HTML
doc = tab.DOM.getDocument()
html = tab.DOM.getOuterHTML(nodeId=doc['root']['nodeId'])
print("HTML length:", len(html['outerHTML']))

tab.stop()
```

### Method 3: Direct WebSocket (Low-Level)

```python
import json
import websocket

# Get WebSocket URL
import requests
version = requests.get('http://localhost:9222/json/version').json()
ws_url = version['webSocketDebuggerUrl']

# Connect
ws = websocket.create_connection(ws_url)

# Send CDP command
def send_command(method, params=None, cmd_id=1):
    msg = {"id": cmd_id, "method": method}
    if params:
        msg["params"] = params
    ws.send(json.dumps(msg))
    return json.loads(ws.recv())

# Example: Get browser version
result = send_command("Browser.getVersion")
print(result)

ws.close()
```

## Best Practices

### Helper Functions

Use these helpers in every CDP script:

```javascript
const fs = require('fs');

// Screenshot helper
async function screenshot(Page, name) {
    const { data } = await Page.captureScreenshot({ format: 'png' });
    const path = `/tmp/chrome-${name}.png`;
    fs.writeFileSync(path, Buffer.from(data, 'base64'));
    return path;
}

// Sleep helper
const sleep = ms => new Promise(r => setTimeout(r, ms));

// Click at coordinates
async function clickAt(Input, x, y) {
    await Input.dispatchMouseEvent({ type: 'mousePressed', x, y, button: 'left', clickCount: 1 });
    await Input.dispatchMouseEvent({ type: 'mouseReleased', x, y, button: 'left', clickCount: 1 });
    await sleep(500);
}

// Click button by text - ALWAYS query fresh positions, never cache
async function clickButton(Runtime, Input, buttonText) {
    const pos = await Runtime.evaluate({
        expression: `
            const btn = Array.from(document.querySelectorAll('button'))
                .find(b => b.textContent.trim() === '${buttonText}');
            if (btn) {
                const rect = btn.getBoundingClientRect();
                JSON.stringify({ x: rect.x + rect.width/2, y: rect.y + rect.height/2 });
            }
        `,
        returnByValue: true
    });
    if (pos.result.value) {
        const {x, y} = JSON.parse(pos.result.value);
        await clickAt(Input, x, y);
        return true;
    }
    return false;
}

// Check for blocking overlays (modals, dialogs, popups)
async function hasBlockingOverlay(Runtime) {
    const result = await Runtime.evaluate({
        expression: `
            const selectors = '.modal, [role="dialog"], .overlay, .popup, .dialog';
            const overlays = document.querySelectorAll(selectors);
            Array.from(overlays).some(el => {
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== 'none'
                    && style.visibility !== 'hidden'
                    && rect.width > 0;
            });
        `,
        returnByValue: true
    });
    return result.result.value === true;
}

// Try multiple strategies to close overlays
async function closeAnyOverlay(Runtime, Input) {
    // Strategy 1: Press Escape
    await Input.dispatchKeyEvent({ type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
    await Input.dispatchKeyEvent({ type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
    await sleep(300);
    if (!await hasBlockingOverlay(Runtime)) return true;

    // Strategy 2: Click Close/Cancel button
    if (await clickButton(Runtime, Input, 'Close')) {
        await sleep(300);
        if (!await hasBlockingOverlay(Runtime)) return true;
    }
    if (await clickButton(Runtime, Input, 'Cancel')) {
        await sleep(300);
        if (!await hasBlockingOverlay(Runtime)) return true;
    }

    // Strategy 3: Click X button (common patterns)
    const xBtn = await Runtime.evaluate({
        expression: `
            const selectors = '.close, .btn-close, [aria-label="Close"], button:has(svg)';
            const btn = document.querySelector('.modal ' + selectors + ', [role="dialog"] ' + selectors);
            if (btn) {
                const rect = btn.getBoundingClientRect();
                JSON.stringify({ x: rect.x + rect.width/2, y: rect.y + rect.height/2 });
            }
        `,
        returnByValue: true
    });
    if (xBtn.result.value) {
        const {x, y} = JSON.parse(xBtn.result.value);
        await clickAt(Input, x, y);
        await sleep(300);
        if (!await hasBlockingOverlay(Runtime)) return true;
    }

    return false; // Could not close
}
```

### Verify-Act-Verify Pattern

**Never assume an action worked.** Always:

1. Screenshot BEFORE to see current state
2. Check for blocking overlays and close them
3. Perform the action
4. Screenshot AFTER
5. **READ the screenshot** to visually confirm success

```javascript
async function safeClick(Page, Runtime, Input, buttonText, stepName) {
    // 1. Screenshot before
    await screenshot(Page, `${stepName}-1-before`);

    // 2. Clear any blocking overlays
    if (await hasBlockingOverlay(Runtime)) {
        console.log('Overlay detected, closing...');
        await closeAnyOverlay(Runtime, Input);
        await screenshot(Page, `${stepName}-2-overlay-closed`);
    }

    // 3. Perform action
    console.log(`Clicking ${buttonText}...`);
    const clicked = await clickButton(Runtime, Input, buttonText);
    if (!clicked) {
        console.log(`Button "${buttonText}" not found!`);
        return false;
    }

    // 4. Screenshot after - MUST READ THIS to verify
    const path = await screenshot(Page, `${stepName}-3-after`);
    console.log(`Verify result: ${path}`);
    return true;
}

// Usage
await safeClick(Page, Runtime, Input, 'Submit', 'submit-form');
// Then READ /tmp/chrome-submit-form-3-after.png to verify it worked
```

### Why This Matters

| Problem | Solution |
|---------|----------|
| Modals block clicks | Check `hasBlockingOverlay()` before every action |
| Cached coordinates are stale | Always query DOM fresh with `clickButton()` |
| Can't tell if action worked | Screenshot after and READ it |
| Different apps close differently | `closeAnyOverlay()` tries Escape, Close, Cancel, X |

### Common Mistakes

**Bad:** Click then assume success
```javascript
await clickAt(Input, 500, 300);  // Hope it works
```

**Good:** Verify before and after
```javascript
await screenshot(Page, 'before');
if (await hasBlockingOverlay(Runtime)) {
    await closeAnyOverlay(Runtime, Input);
}
await clickButton(Runtime, Input, 'Submit');
await screenshot(Page, 'after');  // READ THIS FILE
```

## Common Operations

### Navigate and Get Content

```javascript
// Navigate
await Page.navigate({ url: 'https://example.com' });
await Page.loadEventFired();

// Get page content
const { root } = await DOM.getDocument();
const { outerHTML } = await DOM.getOuterHTML({ nodeId: root.nodeId });
```

### Click Element

```javascript
// Find element by selector
const { root } = await DOM.getDocument();
const { nodeId } = await DOM.querySelector({
    nodeId: root.nodeId,
    selector: '#my-button'
});

// Get element position
const { model } = await DOM.getBoxModel({ nodeId });
const x = model.content[0] + model.width / 2;
const y = model.content[1] + model.height / 2;

// Click
await Input.dispatchMouseEvent({ type: 'mousePressed', x, y, button: 'left', clickCount: 1 });
await Input.dispatchMouseEvent({ type: 'mouseReleased', x, y, button: 'left', clickCount: 1 });
```

### Type Text

```javascript
// Focus input first
await Runtime.evaluate({
    expression: `document.querySelector('#my-input').focus()`
});

// Type text
for (const char of 'Hello World') {
    await Input.dispatchKeyEvent({ type: 'keyDown', text: char });
    await Input.dispatchKeyEvent({ type: 'keyUp', text: char });
}
```

### Take Screenshot

```javascript
const { data } = await Page.captureScreenshot({ format: 'png' });
require('fs').writeFileSync('screenshot.png', Buffer.from(data, 'base64'));
```

### Execute JavaScript and Get Result

```javascript
const { result } = await Runtime.evaluate({
    expression: `
        // Your JavaScript here
        document.querySelectorAll('a').length
    `,
    returnByValue: true
});
console.log('Link count:', result.value);
```

## Troubleshooting

### "Connection refused" on port 9222

1. Verify Chrome is running with `--remote-debugging-port=9222` on host
2. Verify port is forwarded: `boxctl ports forward 9222`
3. Check from container: `curl http://localhost:9222/json/version`

### "No targets available"

Chrome has no open tabs. Open a tab in Chrome or create one via CDP:

```bash
curl http://localhost:9222/json/new?about:blank
```

### WebSocket connection fails

Use the exact `webSocketDebuggerUrl` from `/json/version` response. Do not construct it manually.

### Multiple clients

CDP supports multiple clients since Chrome 63. If another client disconnects you, you'll receive a `detached` event with reason `replaced_with_devtools`.

## Security Warning

Remote debugging gives **full control** of the browser. Anyone who can connect to port 9222 can:
- Read all page content including passwords
- Execute JavaScript in any page
- Access cookies and session data
- Navigate to any URL

Only enable on trusted networks and ensure firewall blocks external access to port 9222.

## Key CDP Domains

| Domain | Purpose |
|--------|---------|
| Page | Navigation, screenshots, lifecycle |
| Runtime | JavaScript evaluation |
| DOM | Document structure, queries |
| Input | Mouse and keyboard events |
| Network | Request interception, caching |
| Emulation | Device simulation, geolocation |
| Target | Tab management |

Full protocol documentation: https://chromedevtools.github.io/devtools-protocol/
