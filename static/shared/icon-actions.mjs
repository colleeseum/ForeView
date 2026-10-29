// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {escapeHtml} from './html.mjs';

export const ICON_ACTIONS = Object.freeze(['edit', 'delete', 'view', 'download', 'add', 'expand', 'collapse', 'close', 'help', 'reset']);
let sequence = 0;

// Labels are supplied through the shared translator, including the action target.
// Only data/ARIA hooks and ordinary button identifiers are accepted, never HTML events.
export function iconAction(action, {label, attributes = {}, disabled = false, busy = false} = {}) {
  if (!ICON_ACTIONS.includes(action) || typeof label !== 'string' || !label.trim()) throw new TypeError('An icon action requires a known action and a nonempty label');
  const hooks = Object.entries(attributes).map(([name, value]) => {
    if (name === 'data-icon-action' || !/^(?:id|name|value|data-[a-z0-9-]+|aria-(?:expanded|controls|pressed|describedby))$/.test(name)) throw new TypeError('Unsupported icon action attribute');
    return ` ${name}="${escapeHtml(value)}"`;
  }).join('');
  return `<button type="button" class="fv-button fv-icon-action${action === 'delete' ? ' fv-button--danger' : ''}" data-icon-action="${action}" aria-label="${escapeHtml(label)}"${hooks}${disabled || busy ? ' disabled' : ''}${busy ? ' aria-busy="true"' : ''}><span class="fv-icon fv-icon--${action}" aria-hidden="true"></span></button>`;
}

// Event delegation covers controls inserted by table refreshes. Install once per
// workspace, and destroy when unmounting. Tooltip text never interprets HTML.
export function initializeIconActions(root = document) {
  const doc = root.ownerDocument || root;
  const win = doc.defaultView;
  let anchor = null;
  let tooltip = null;
  let suppressed = null;
  let hovered = null;
  let tooltipHovered = false;
  let hideTimer = null;
  function cancelHide() {
    if (hideTimer !== null) {win.clearTimeout(hideTimer); hideTimer = null;}
  }
  function hide() {
    cancelHide();
    if (!tooltip) return;
    const ids = (anchor.getAttribute('aria-describedby') || '').split(/\s+/).filter(id => id && id !== tooltip.id);
    if (ids.length) anchor.setAttribute('aria-describedby', ids.join(' '));
    else anchor.removeAttribute('aria-describedby');
    tooltip.remove();
    anchor = tooltip = null;
    tooltipHovered = false;
  }
  function control(node) {
    const button = node?.closest?.('[data-icon-action]');
    return button && root.contains(button) ? button : null;
  }
  function unavailable(button) {
    return button.matches(':disabled, [aria-disabled="true"], [aria-busy="true"]');
  }
  function show(button) {
    cancelHide();
    if (!button || button === suppressed || unavailable(button)) return;
    if (anchor === button) return;
    hide();
    const label = button.getAttribute('aria-label');
    if (!label) return;
    anchor = button;
    tooltip = doc.createElement('span');
    tooltip.id = `fv-icon-tip-${++sequence}`;
    tooltip.className = 'fv-icon-tooltip';
    tooltip.setAttribute('role', 'tooltip');
    tooltip.textContent = label;
    const style = win.getComputedStyle(button);
    for (const property of ['--fv-control-border', '--fv-radius-control', '--fv-surface', '--fv-text', '--fv-type-detail', '--fv-font']) {
      const value = style.getPropertyValue(property);
      if (value) tooltip.style.setProperty(property, value);
    }
    tooltip.lang = button.closest('[lang]')?.lang || doc.documentElement.lang;
    (button.closest('dialog[open]') || doc.body).append(tooltip);
    anchor.setAttribute('aria-describedby', [anchor.getAttribute('aria-describedby'), tooltip.id].filter(Boolean).join(' '));
    position();
  }
  function position() {
    if (!anchor || !tooltip) return;
    const rect = anchor.getBoundingClientRect();
    const box = tooltip.getBoundingClientRect();
    const rtl = win.getComputedStyle(anchor).direction === 'rtl';
    tooltip.dir = rtl ? 'rtl' : 'ltr';
    const x = rtl ? rect.right - box.width : rect.left;
    tooltip.style.left = `${Math.max(8, Math.min(x, win.innerWidth - box.width - 8))}px`;
    const y = rect.bottom + 6 + box.height <= win.innerHeight - 8 ? rect.bottom + 6 : rect.top - box.height - 6;
    tooltip.style.top = `${Math.max(8, y)}px`;
  }
  function enter(event) {
    if (tooltip?.contains(event.target)) {tooltipHovered = true; cancelHide(); return;}
    const button = control(event.target);
    if (!button || button.contains(event.relatedTarget)) return;
    if (event.type === 'pointerover') hovered = button;
    suppressed = null;
    show(button);
  }
  function leave(event) {
    if (!anchor || (!anchor.contains(event.target) && !tooltip.contains(event.target))) return;
    if (event.type === 'pointerout') {
      if (anchor.contains(event.relatedTarget) || tooltip.contains(event.relatedTarget)) {
        hovered = anchor.contains(event.relatedTarget) ? anchor : null;
        tooltipHovered = tooltip.contains(event.relatedTarget);
        return;
      }
      if (anchor.contains(event.target)) hovered = null;
      tooltipHovered = false;
      if (doc.activeElement === anchor) return;
      cancelHide();
      // Allow the pointer to cross the small gap into the hoverable tooltip.
      hideTimer = win.setTimeout(hide, 150);
    } else if (hovered !== anchor && !tooltipHovered) hide();
  }
  function keydown(event) {
    if (tooltip && event.target === anchor && ['PageDown', 'PageUp'].includes(event.key) && tooltip.scrollHeight > tooltip.clientHeight) {
      tooltip.scrollTop += (event.key === 'PageDown' ? 1 : -1) * tooltip.clientHeight;
      event.preventDefault();
      return;
    }
    if (event.key !== 'Escape' || !tooltip) return;
    suppressed = anchor;
    hide();
    // Escape dismisses the tooltip first, without also dismissing its modal.
    event.preventDefault();
    event.stopPropagation();
  }
  const events = [['focusin', enter], ['pointerover', enter], ['focusout', leave], ['pointerout', leave], ['click', hide]];
  for (const [name, handler] of events) doc.addEventListener(name, handler);
  doc.addEventListener('keydown', keydown, true);
  win.addEventListener('resize', position);
  win.addEventListener('scroll', position, true);
  const observer = new win.MutationObserver(() => {if (anchor && (!root.contains(anchor) || unavailable(anchor))) hide();});
  observer.observe(root, {childList: true, subtree: true, attributes: true, attributeFilter: ['disabled', 'aria-disabled', 'aria-busy']});
  return {destroy() {
    hide();
    observer.disconnect();
    for (const [name, handler] of events) doc.removeEventListener(name, handler);
    doc.removeEventListener('keydown', keydown, true);
    win.removeEventListener('resize', position);
    win.removeEventListener('scroll', position, true);
  }};
}
