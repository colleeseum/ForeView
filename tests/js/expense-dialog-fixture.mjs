// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

// Mirror native dialog markup, shimming only browser-provided methods for jsdom.
export function installExpenseDialogs(dom) {
  for (const old of dom.window.document.querySelectorAll('[id$="-backdrop"]')) {
    const dialog = dom.window.document.createElement('dialog');
    dialog.id = old.id;
    dialog.hidden = old.hidden;
    dialog.append(...old.childNodes);
    old.replaceWith(dialog);
    dialog.showModal = () => {dialog.open = true;};
    dialog.close = () => {dialog.open = false; dialog.dispatchEvent(new dom.window.Event('close'));};
  }
}
