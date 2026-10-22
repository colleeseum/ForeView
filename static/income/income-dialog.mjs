// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {createDialog} from '../shared/dialog.mjs';
import {t, locale} from '../shared/i18n.mjs';

// Preserve field state (including a locked tax year) across pending operations.
export function createIncomeDialog(dialog, fallbackFocus) {
  const controller = createDialog(dialog, {fallbackFocus});
  let busy = false;
  let controls = [];
  let invoker = null;
  let action = null;
  const actionAttributes = ['data-correct-concept', 'data-edit-year'];
  dialog.addEventListener('cancel', event => {if (busy) event.preventDefault();});
  dialog.addEventListener('close', () => {
    if (dialog.open) return;
    dialog.hidden = true;
    if (invoker && !invoker.isConnected && action) {
      const replacement = [...document.querySelectorAll(`[${action[0]}]`)]
        .find(node => node.getAttribute(action[0]) === action[1]);
      replacement?.focus();
    }
    if (document.activeElement === document.body || dialog.contains(document.activeElement) || document.activeElement.matches(':disabled')) {
      document.querySelector('#income-retry:not([hidden])')?.focus();
    }
  });
  // Help is rendered inside the native top layer, not in an inert legacy drawer.
  dialog.addEventListener('click', async event => {
    const button = event.target.closest('[data-help-article], [data-help-tooltip]');
    if (!button) return;
    event.stopPropagation();
    let panel = dialog.querySelector('[data-inline-help]');
    if (!panel) {
      panel = document.createElement('section');
      panel.dataset.inlineHelp = '';
      panel.className = 'fv-feedback';
      panel.tabIndex = -1;
      panel.setAttribute('role', 'status');
      button.after(panel);
    }
    panel.hidden = false;
    panel.textContent = t('help.loading');
    panel.focus();
    try {
      const response = await fetch('/api/help');
      if (!response.ok) throw new Error(t('help.unavailable'));
      const catalog = await response.json();
      const content = (button.dataset.helpArticle ? catalog.articles : catalog.tooltips)
        .find(item => item.key === (button.dataset.helpArticle || button.dataset.helpTooltip));
      if (!content) throw new Error(t('help.unavailable'));
      panel.replaceChildren(...['title', 'summary', 'body'].filter(field => content[field]).map(field => {
        const node = document.createElement(field === 'title' ? 'strong' : 'p');
        node.textContent = content[field];
        node.lang = content.field_languages?.[field] || content.language || catalog.language || locale;
        return node;
      }));
    } catch (error) {panel.textContent = error.message;}
  });
  return {
    get busy() {return busy;},
    open() {
      invoker = document.activeElement;
      const attribute = actionAttributes.find(name => invoker.hasAttribute(name));
      action = attribute ? [attribute, invoker.getAttribute(attribute)] : null;
      dialog.hidden = false;
      controller.open(invoker);
    },
    close() {
      if (busy) return;
      controller.close();
    },
    setBusy(value) {
      if (busy === value) return;
      busy = value;
      dialog.setAttribute('aria-busy', String(busy));
      if (busy) {
        controls = [...dialog.querySelectorAll('input, select, textarea, button')].map(node => [node, node.disabled]);
        controls.forEach(([node]) => {node.disabled = true;});
      } else {
        controls.forEach(([node, disabled]) => {node.disabled = disabled;});
        controls = [];
      }
    },
  };
}
