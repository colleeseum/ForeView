// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

// Native showModal supplies inert background, initial autofocus and Escape.
// Explicit edge wrapping keeps Tab inside rather than moving to browser chrome.
// Callers own labels, validation, dirty-form policy and post-save feedback.
export function createDialog(dialog, {fallbackFocus = null} = {}) {
  let trigger = null;
  let restorePending = false;
  function restoreFocus() {
    if (!restorePending || dialog.open) return;
    for (const target of [trigger, fallbackFocus]) {
      if (!target?.isConnected || target.matches(':disabled')) continue;
      target.focus();
      // Connected controls can become hidden/inert or otherwise unfocusable.
      if (dialog.ownerDocument.activeElement === target) break;
    }
    trigger = null;
    restorePending = false;
  }
  function close() {
    if (dialog.open) {
      dialog.close();
      restoreFocus();
    }
  }
  function dismiss(event) {
    if (event.target.closest('dialog') === dialog && event.target.closest('[data-dialog-close]')) close();
  }
  function containTab(event) {
    if (event.defaultPrevented || event.key !== 'Tab' || event.target.closest('dialog') !== dialog) return;
    const active = dialog.ownerDocument.activeElement;
    const candidates = [...dialog.querySelectorAll('button, input, select, textarea, a[href], summary, [tabindex], [contenteditable]')]
      .filter(node => {
        // Editing hosts are native tab stops despite reporting tabIndex=-1.
        // Nested editors need an explicit tabindex to join sequential navigation.
        const editingHost = !node.hasAttribute('tabindex')
          && node.matches('[contenteditable=""], [contenteditable="true" i], [contenteditable="plaintext-only" i]')
          && !node.parentElement?.isContentEditable;
        const visibility = dialog.ownerDocument.defaultView.getComputedStyle(node).visibility;
        return node.closest('dialog') === dialog && !node.matches(':disabled')
          && (node.tabIndex >= 0 || editingHost) && node.getClientRects().length
          && visibility !== 'hidden' && visibility !== 'collapse'
          && !node.closest('[inert], [hidden]');
      });
    const controls = candidates.filter(node => {
      if (!node.matches('input[type="radio"]') || !node.name) return true;
      const group = candidates.filter(other => other.matches('input[type="radio"]')
        && other.name === node.name && other.form === node.form && other.getRootNode() === node.getRootNode());
      // A named radio group contributes one tab stop, not each member.
      const stop = group.find(radio => radio.checked)
        || (group.includes(active) ? active : event.shiftKey ? group.at(-1) : group[0]);
      return node === stop;
    });
    const first = controls[0];
    const last = controls.at(-1);
    if (!first) {event.preventDefault(); return;}
    // Autofocus may intentionally land on a heading with tabindex=-1.
    if (event.shiftKey && (active === first || !controls.includes(active))) {event.preventDefault(); last.focus();}
    else if (!event.shiftKey && active === last) {event.preventDefault(); first.focus();}
  }
  dialog.addEventListener('close', restoreFocus);
  dialog.addEventListener('click', dismiss);
  dialog.addEventListener('keydown', containTab);
  return {
    open(invoker = dialog.ownerDocument.activeElement) {
      if (dialog.open) return;
      dialog.showModal();
      trigger = invoker;
      restorePending = true;
    },
    close,
    destroy() {
      close();
      restoreFocus();
      dialog.removeEventListener('close', restoreFocus);
      dialog.removeEventListener('click', dismiss);
      dialog.removeEventListener('keydown', containTab);
    },
  };
}
