// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

// Presentation only. Feature controllers retain their HTTP and persistence contracts.
import {t} from '../shared/i18n.mjs';

const root = document.querySelector('.fv-admin');
let regionCount = 0;
export function enhanceAdministration(container) {
  container.querySelectorAll('button, a.view-action').forEach(node => {
    node.classList.add('fv-button');
    if (node.matches('button[type="submit"]')) node.classList.add('fv-button--primary');
  });
  container.querySelectorAll('input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]), select, textarea').forEach(node => node.classList.add('fv-input'));
  container.querySelectorAll('table').forEach(table => {
    table.classList.add('fv-table');
    const title = table.closest('section')?.querySelector('h2')?.textContent || t('administration.reference');
    if (!table.caption) table.createCaption().textContent = title;
    table.querySelectorAll('thead th').forEach(node => {node.scope = 'col';});
    let region = table.parentElement;
    if (!region.classList.contains('fv-table-scroll')) {
      // Keep a table's own source/details siblings outside its scroll region.
      region = document.createElement('div');
      table.before(region);
      region.append(table);
      region.className = 'fv-table-scroll';
      region.tabIndex = 0;
      region.setAttribute('role', 'region');
      region.setAttribute('aria-label', title);
      const hint = document.createElement('p');
      hint.className = 'fv-help';
      hint.id = `administration-table-hint-${++regionCount}`;
      hint.textContent = t('administration.scroll_hint');
      region.prepend(hint);
      region.setAttribute('aria-describedby', hint.id);
    }
  });
}
if (root) {
  enhanceAdministration(root);
  new MutationObserver(() => enhanceAdministration(root)).observe(root, {childList: true, subtree: true});
}
