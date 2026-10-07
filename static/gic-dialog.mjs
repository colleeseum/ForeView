// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {saveJson} from './accounts-api.mjs';
import {assetState} from './accounts-state.mjs';
import {showError} from './form-state.mjs';

const dialog = document.querySelector('#subaccount-dialog');
const form = document.querySelector('#subaccount-dialog-form');
const title = document.querySelector('#subaccount-dialog-title');
const message = document.querySelector('#subaccount-dialog-message');
const parentField = document.querySelector('#subaccount-parent');

let saved = async () => {};

function loadParents(selectedId) {
  parentField.replaceChildren();
  assetState.accounts.filter((account) => account.asset_kind !== 'gic').forEach((account) => {
    const label = `${account.account_number} · ${account.institution || ''} ${account.name || ''}`;
    parentField.add(new Option(label, account.id, false, account.id === selectedId));
  });
}

export function openGicDialog(accountId = null, parentId = null) {
  const account = assetState.accounts.find((item) => item.id === accountId);
  title.textContent = account ? title.dataset.editText : title.dataset.addText;
  message.textContent = '';
  message.classList.remove('error');
  form.querySelector('button[type="submit"]').disabled = false;
  form.reset();
  loadParents(account ? account.parent_account_id : parentId);
  form.balance_date.value = new Date().toISOString().slice(0, 10);
  if (account) {
    form.parent_account_id.value = account.parent_account_id;
    form.account_number.value = account.account_number || '';
    form.name.value = account.name || '';
    form.start_date.value = account.start_date || '';
    form.maturity_date.value = account.maturity_date || '';
    form.principal.value = account.principal == null ? '' : account.principal;
    form.maturity_value.value = account.maturity_value == null ? '' : account.maturity_value;
    form.redeemable.checked = Boolean(account.redeemable);
    form.balance_date.value = account.latest_date || form.balance_date.value;
    form.balance_amount.value = account.latest_amount == null ? '' : account.latest_amount;
    form.interest_rate.value = account.interest_rate == null ? '' : (Number(account.interest_rate) * 100).toFixed(2);
  }
  form.dataset.editingId = accountId || '';
  dialog.hidden = false;
}

export function initializeGicDialog(onSaved) {
  saved = onSaved;
  document.querySelector('#close-subaccount-dialog').addEventListener('click', () => { dialog.hidden = true; });
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const saveButton = form.querySelector('button[type="submit"]');
    saveButton.disabled = true;
    const values = Object.fromEntries(new FormData(form));
    const parent = assetState.accounts.find((item) => item.id === Number(values.parent_account_id));
    const editingId = Number(form.dataset.editingId || 0);
    const payload = {
      ...values,
      asset_kind: 'gic',
      redeemable: form.redeemable.checked,
      category: parent.account_type,
      institution: parent.institution,
    };
    try {
      await saveJson(
        editingId ? `/api/model/accounts/${editingId}` : '/api/model/accounts',
        editingId ? 'PUT' : 'POST',
        payload,
      );
      dialog.hidden = true;
      await saved();
    } catch (error) {
      showError(message, error);
      saveButton.disabled = false;
    }
  });
}
