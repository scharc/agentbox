// PWA initialization - service worker registration and install prompt handling

// Store the install prompt event for later use
let deferredPrompt = null;

// Register service worker
if ('serviceWorker' in navigator) {
    window.addEventListener('load', async () => {
        try {
            const registration = await navigator.serviceWorker.register('/static/service-worker.js', {
                scope: '/'
            });
            console.log('Service Worker registered:', registration.scope);

            // Check for updates periodically
            setInterval(() => {
                registration.update();
            }, 60 * 60 * 1000); // Check every hour

            // Handle updates
            registration.addEventListener('updatefound', () => {
                const newWorker = registration.installing;
                if (newWorker) {
                    newWorker.addEventListener('statechange', () => {
                        if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                            // New version available
                            showUpdateNotification();
                        }
                    });
                }
            });
        } catch (error) {
            console.error('Service Worker registration failed:', error);
        }
    });
}

// Handle install prompt
window.addEventListener('beforeinstallprompt', (e) => {
    // Prevent the mini-infobar from appearing
    e.preventDefault();
    // Store the event for later use
    deferredPrompt = e;
    console.log('Install prompt available');
});

// Show install prompt when user clicks install button (if added to UI)
async function showInstallPrompt() {
    if (!deferredPrompt) {
        console.log('Install prompt not available');
        return false;
    }

    // Show the install prompt
    deferredPrompt.prompt();

    // Wait for user response
    const { outcome } = await deferredPrompt.userChoice;
    console.log('Install prompt outcome:', outcome);

    // Clear the deferred prompt
    deferredPrompt = null;

    return outcome === 'accepted';
}

// Track successful installs
window.addEventListener('appinstalled', () => {
    console.log('PWA installed successfully');
    deferredPrompt = null;
});

// Show update notification
function showUpdateNotification() {
    // Create notification element if it doesn't exist
    let notification = document.getElementById('pwa-update-notification');
    if (!notification) {
        notification = document.createElement('div');
        notification.id = 'pwa-update-notification';
        notification.setAttribute('role', 'alert');
        notification.setAttribute('aria-live', 'polite');
        notification.innerHTML = `
            <span>A new version is available</span>
            <button id="pwa-update-btn" aria-label="Update to new version">Update</button>
            <button id="pwa-dismiss-btn" aria-label="Dismiss notification">&times;</button>
        `;
        notification.style.cssText = `
            position: fixed;
            bottom: 70px;
            left: 50%;
            transform: translateX(-50%);
            background: var(--surface-color, #2a2a2a);
            color: var(--text-color, #e0e0e0);
            padding: 0.75rem 1rem;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            display: flex;
            align-items: center;
            gap: 0.75rem;
            z-index: 1000;
            font-size: 0.9rem;
        `;
        document.body.appendChild(notification);

        // Style buttons
        const updateBtn = document.getElementById('pwa-update-btn');
        updateBtn.style.cssText = `
            background: var(--primary-color, #4a90e2);
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.85rem;
        `;
        updateBtn.addEventListener('click', () => {
            // Tell service worker to skip waiting and activate
            if (navigator.serviceWorker.controller) {
                navigator.serviceWorker.controller.postMessage({ type: 'SKIP_WAITING' });
            }
            // Reload to get new version
            window.location.reload();
        });

        const dismissBtn = document.getElementById('pwa-dismiss-btn');
        dismissBtn.style.cssText = `
            background: none;
            border: none;
            color: var(--text-muted, #aaa);
            cursor: pointer;
            font-size: 1.25rem;
            padding: 0.25rem;
        `;
        dismissBtn.addEventListener('click', () => {
            notification.remove();
        });
    }
}

// Offline/online status indicator
function updateOnlineStatus() {
    const isOnline = navigator.onLine;
    document.body.classList.toggle('offline', !isOnline);

    if (!isOnline) {
        console.log('App is offline');
    } else {
        console.log('App is online');
    }
}

window.addEventListener('online', updateOnlineStatus);
window.addEventListener('offline', updateOnlineStatus);
updateOnlineStatus();

// Export for potential external use
window.PWA = {
    showInstallPrompt,
    isInstallable: () => deferredPrompt !== null
};
