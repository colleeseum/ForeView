// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {createDialog} from '../shared/dialog.mjs';
import {t} from '../shared/i18n.mjs';

// Preserve hidden-state consumers while adopting the native modal lifecycle.
export function createAssetDialog(dialog) {
  const controller = createDialog(dialog);
  let trigger = null;
  let action = null;
  let busy = false;
  let controls = [];
  let submitText = '';
  const actions = ['data-edit-account', 'data-add-account-type', 'data-add-subaccount', 'data-edit-real-estate', 'data-add-real-estate'];
  function finishClose() {
    if (dialog.open) return;
    dialog.hidden = true;
    if (trigger && !trigger.isConnected) {
      const replacement = action && [...dialog.ownerDocument.querySelectorAll(`[${action[0]}]`)]
        .find(node => node.getAttribute(action[0]) === action[1]);
      (replacement || dialog.ownerDocument.querySelector('.view-tab.active'))?.focus();
    }
  }
  dialog.addEventListener('close', finishClose);
  dialog.addEventListener('cancel', event => {if (busy) event.preventDefault();});
  return {
    get busy() { return busy; },
    setBusy(value) {
      if (busy === value) return;
      busy = value;
      dialog.setAttribute('aria-busy', String(busy));
      const submit = dialog.querySelector('button[type="submit"]');
      if (busy) {
        controls = [...dialog.querySelectorAll('input, select, textarea, button')].map(node => [node, node.disabled]);
        controls.forEach(([node]) => {node.disabled = true;});
        submitText = submit.textContent;
        submit.textContent = t('accounts.saving');
      } else {
        controls.forEach(([node, disabled]) => {node.disabled = disabled;});
        controls = [];
        submit.textContent = submitText;
      }
    },
    open() {
      trigger = dialog.ownerDocument.activeElement;
      const attribute = actions.find(name => trigger.hasAttribute(name));
      action = attribute ? [attribute, trigger.getAttribute(attribute)] : null;
      dialog.querySelector('input:not([type="checkbox"]), select').autofocus = true;
      dialog.hidden = false;
      controller.open(trigger);
    },
    close() {
      if (busy) return;
      controller.close();
      finishClose();
    },
  };
}
