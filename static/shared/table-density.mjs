// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

// Presentation-only, browser-origin preference. Storage denial must not break UI.
export function initializeTableDensity(select, root, storageKey) {
  const view = select.ownerDocument.defaultView;
  function apply(value) {
    const density = value === 'compact' ? 'compact' : 'standard';
    select.value = density;
    root.dataset.tableDensity = density;
  }
  let saved = null;
  try { saved = view.localStorage.getItem(storageKey); } catch { /* Private/restricted storage. */ }
  apply(saved);
  select.addEventListener('change', () => {
    apply(select.value);
    try { view.localStorage.setItem(storageKey, select.value); } catch { /* Keep current-page choice. */ }
  });
}
