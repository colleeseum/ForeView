// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {saveJson} from './accounts-api.mjs';
import {ownerDetails} from './accounts-format.mjs';
import {assetState} from './accounts-state.mjs';
import {formSignature, showError} from '../shared/form-state.mjs';
import {ownershipSignature, renderOwnershipFields, selectedOwners} from './ownership-fields.mjs';
import {createAssetDialog} from './asset-dialog.mjs';

const dialog = document.querySelector('#account-dialog');
const modal = createAssetDialog(dialog);
const form = document.querySelector('#account-dialog-form');
const title = document.querySelector('#account-dialog-title');
const message = document.querySelector('#account-dialog-message');
const ownerFields = document.querySelector('#dialog-owner-fields');
const saveButton = form.querySelector('button[type="submit"], button:not([type])');

let baseline = '';
let editingId = null;
let saved = async () => {};

function closeDialog() {
  modal.close();
}

function signature() {
  return formSignature(form, ownershipSignature(ownerFields));
}

function updateSaveButton() {
  saveButton.disabled = signature() === baseline;
}

export function openAccountDialog(accountId = null, category = 'non_registered') {
  editingId = accountId;
  const account = assetState.accounts.find((item) => item.id === accountId);
  title.textContent = account ? title.dataset.editText : title.dataset.addText;
  message.textContent = '';
  message.classList.remove('error');
  form.reset();
  form.balance_date.value = new Date().toISOString().slice(0, 10);
  form.category.value = category;
  if (account) {
    form.account_number.value = account.account_number || '';
    form.institution.value = account.institution || '';
    form.name.value = account.name || '';
    form.category.value = account.account_type;
    form.balance_date.value = account.latest_date || form.balance_date.value;
    form.balance_amount.value = account.latest_amount == null ? '' : account.latest_amount;
    form.interest_rate.value = account.interest_rate == null ? '' : (Number(account.interest_rate) * 100).toFixed(2);
  }
  renderOwnershipFields(ownerFields, assetState.people, account ? ownerDetails(account) : [], updateSaveButton);
  baseline = signature();
  updateSaveButton();
  modal.open();
}

export function initializeAccountDialog(onSaved) {
  saved = onSaved;
  document.querySelector('#close-account-dialog').addEventListener('click', closeDialog);
  document.querySelector('#cancel-account-dialog')?.addEventListener('click', closeDialog);
  form.addEventListener('input', updateSaveButton);
  form.addEventListener('change', updateSaveButton);
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (modal.busy) return;
    const values = Object.fromEntries(new FormData(form));
    const payload = {...values, owners: selectedOwners(ownerFields)};
    if (!editingId) payload.asset_kind = 'account';
    modal.setBusy(true);
    try {
      await saveJson(
        editingId ? `/api/model/accounts/${editingId}` : '/api/model/accounts',
        editingId ? 'PUT' : 'POST',
        payload,
      );
      await saved();
      modal.setBusy(false);
      modal.close();
    } catch (error) {
      showError(message, error);
      updateSaveButton();
    } finally {
      modal.setBusy(false);
    }
  });
}
