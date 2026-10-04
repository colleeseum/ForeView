// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

(() => {
  const token = document.querySelector('meta[name="csrf-token"]')?.content;
  const originalFetch = window.fetch.bind(window);
  const unsafeMethods = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

  window.fetch = (input, options = {}) => {
    const request = input instanceof Request ? input : null;
    const method = String(options.method || request?.method || 'GET').toUpperCase();
    const url = new URL(request?.url || String(input), window.location.href);
    if (!token || !unsafeMethods.has(method) || url.origin !== window.location.origin) {
      return originalFetch(input, options);
    }
    const headers = new Headers(options.headers || request?.headers);
    headers.set('X-CSRF-Token', token);
    return originalFetch(input, {...options, headers});
  };
})();
