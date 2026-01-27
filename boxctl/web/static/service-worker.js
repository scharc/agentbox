// Service Worker for boxctl PWA
// Implements caching strategy for offline support

const CACHE_VERSION = 'v1';
const CACHE_NAME = `boxctl-${CACHE_VERSION}`;

// Static assets to cache
const STATIC_ASSETS = [
  '/',
  '/static/css/style.css',
  '/static/js/session-list.js',
  '/static/js/terminal.js',
  '/static/js/keybar.js',
  '/static/js/pwa-handler.js',
  '/static/js/session-peek.js',
  '/static/js/offline-cache.js',
  '/static/index.html',
  '/static/terminal.html',
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/maskable-icon.png',
  'https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.min.js',
  'https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.min.css',
  'https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.min.js',
];

// Install event - cache static assets
self.addEventListener('install', (event) => {
  console.log('[ServiceWorker] Installing version:', CACHE_VERSION);

  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('[ServiceWorker] Caching static assets');
        // Use addAll with individual error handling to prevent one failure from breaking all
        return Promise.all(
          STATIC_ASSETS.map((url) =>
            cache.add(url).catch((err) => {
              console.warn(`[ServiceWorker] Failed to cache ${url}:`, err.message);
            })
          )
        );
      })
      .then(() => {
        console.log('[ServiceWorker] Installation complete');
        // Activate immediately
        return self.skipWaiting();
      })
      .catch((err) => {
        console.error('[ServiceWorker] Installation failed:', err);
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  console.log('[ServiceWorker] Activating version:', CACHE_VERSION);

  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames
            .filter((name) => name.startsWith('boxctl-') && name !== CACHE_NAME)
            .map((name) => {
              console.log('[ServiceWorker] Deleting old cache:', name);
              return caches.delete(name);
            })
        );
      })
      .then(() => {
        console.log('[ServiceWorker] Activation complete');
        // Take control of all pages immediately
        return self.clients.claim();
      })
  );
});

// Fetch event - implement caching strategy
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== 'GET') {
    return;
  }

  // Skip WebSocket connections
  if (url.protocol === 'ws:' || url.protocol === 'wss:') {
    return;
  }

  // Strategy: Network-first for API calls, cache-first for static assets
  if (url.pathname.startsWith('/api/')) {
    // Network-first strategy for API calls (always try network first)
    event.respondWith(
      fetch(request)
        .then((response) => {
          // Cache successful API responses
          if (response.ok) {
            const responseClone = response.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(request, responseClone);
            });
          }
          return response;
        })
        .catch(() => {
          // Fallback to cache if network fails
          return caches.match(request).then((cached) => {
            if (cached) {
              return cached;
            }
            // Return offline response for API calls
            return new Response(
              JSON.stringify({
                offline: true,
                message: 'You are currently offline. Please check your connection.',
              }),
              {
                status: 503,
                headers: { 'Content-Type': 'application/json' },
              }
            );
          });
        })
    );
  } else if (url.pathname.startsWith('/ws/')) {
    // Don't handle WebSocket endpoints
    return;
  } else {
    // Cache-first strategy for static assets
    event.respondWith(
      caches.match(request).then((cached) => {
        if (cached) {
          // Return cached version and update in background
          fetch(request)
            .then((response) => {
              if (response.ok) {
                caches.open(CACHE_NAME).then((cache) => {
                  cache.put(request, response);
                });
              }
            })
            .catch(() => {
              // Silently fail background update
            });
          return cached;
        }

        // Fetch from network if not cached
        return fetch(request)
          .then((response) => {
            // Cache successful responses
            if (response.ok) {
              const responseClone = response.clone();
              caches.open(CACHE_NAME).then((cache) => {
                cache.put(request, responseClone);
              });
            }
            return response;
          })
          .catch(() => {
            // Return offline page for navigation requests
            if (request.mode === 'navigate') {
              return caches.match('/').then((cached) => {
                if (cached) {
                  return cached;
                }
                return new Response(
                  '<h1>Offline</h1><p>You are currently offline.</p>',
                  {
                    status: 503,
                    headers: { 'Content-Type': 'text/html' },
                  }
                );
              });
            }
            throw new Error('Network request failed and no cache available');
          });
      })
    );
  }
});

// Listen for messages from clients
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }

  if (event.data && event.data.type === 'CHECK_UPDATE') {
    // Force update check
    self.registration.update();
  }
});

// Periodic background sync (if supported)
self.addEventListener('sync', (event) => {
  console.log('[ServiceWorker] Background sync:', event.tag);

  if (event.tag === 'sync-sessions') {
    event.waitUntil(
      fetch('/api/sessions')
        .then((response) => response.json())
        .then((data) => {
          // Cache updated session data
          const cache = caches.open(CACHE_NAME);
          return cache.then((c) =>
            c.put('/api/sessions', new Response(JSON.stringify(data)))
          );
        })
        .catch((err) => {
          console.error('[ServiceWorker] Background sync failed:', err);
        })
    );
  }
});

console.log('[ServiceWorker] Loaded version:', CACHE_VERSION);
