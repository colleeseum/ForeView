// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {escapeHtml} from './html.mjs';
import {t, locale} from './i18n.mjs';
import {accountTypeLabel} from './account-types.mjs';
import {editableAccountValues} from './setup-values.mjs';

const message = document.querySelector('#setup-message');
const peopleList = document.querySelector('#people-list');
const accountsList = document.querySelector('#accounts-list');
const ownerFields = document.querySelector('#owner-fields');
const accountSelectors = [document.querySelector('#balance-account'), document.querySelector('#gic-account')];
function accountLabel(account) {
  if (account.asset_kind === 'gic') return `${t('accounts.gic')} · ${account.name || t('setup.unnamed')}`;
  return `${account.account_number || ''} · ${account.institution || ''} ${account.name || ''}`;
}
let people = [];
let accounts = [];

function trackFormChanges(form) {
  const button = form.querySelector('button[type="submit"], button:not([type])');
  const signature = () => JSON.stringify([...form.elements].map((field) => ({name: field.name, type: field.type, value: field.type === 'checkbox' ? field.checked : field.value})));
  let baseline = signature();
  const update = () => { button.disabled = signature() === baseline; };
  form.addEventListener('input', update);
  form.addEventListener('change', update);
  return () => { baseline = signature(); button.disabled = true; };
}

const resetPersonFormState = trackFormChanges(document.querySelector('#person-form'));
const resetAccountFormState = trackFormChanges(document.querySelector('#account-form'));
const resetBalanceFormState = trackFormChanges(document.querySelector('#balance-form'));
const resetGicFormState = trackFormChanges(document.querySelector('#gic-form'));
const resetScenarioFormState = trackFormChanges(document.querySelector('#scenario-form'));

document.querySelectorAll('.setup-tab').forEach((tab) => tab.addEventListener('click', () => {
  document.querySelectorAll('.setup-tab').forEach((item) => item.classList.toggle('active', item === tab));
  document.querySelectorAll('.setup-panel').forEach((panel) => panel.classList.toggle('active', panel.id === tab.dataset.tab));
}));

function showMessage(text, error = false, language = locale) {
  message.textContent = text;
  message.className = `form-message${error ? ' error' : ''}`;
  message.lang = language;
}

function showError(error) {
  showMessage(error.message, true, error.language || 'en-CA');
}

async function api(url, options = {}) {
  const response = await fetch(url, {headers: {'Content-Type': 'application/json'}, ...options});
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.error || t('setup.request_failed'));
    error.language = data.error ? 'en-CA' : locale;
    throw error;
  }
  return data;
}

function renderPeople() {
  peopleList.replaceChildren(...people.map((person) => {
    const item = document.createElement('li');
    item.innerHTML = `<strong>${escapeHtml(person.name)}</strong><label class="inline-date">${t('setup.birth_date')}<input type="date" data-birth-date="${Number(person.id)}" data-original-date="${escapeHtml(person.birth_date)}" value="${escapeHtml(person.birth_date)}" required></label><button type="button" data-save-person="${Number(person.id)}" hidden>${t('setup.save')}</button>`;
    return item;
  }));
  peopleList.querySelectorAll('[data-birth-date]').forEach((input) => input.addEventListener('input', () => {
    const saveButton = peopleList.querySelector(`[data-save-person="${input.dataset.birthDate}"]`);
    saveButton.hidden = input.value === input.dataset.originalDate;
  }));
  peopleList.querySelectorAll('[data-save-person]').forEach((button) => button.addEventListener('click', async () => {
    const personId = button.dataset.savePerson;
    const birthDate = peopleList.querySelector(`[data-birth-date="${personId}"]`).value;
    try { await api(`/api/model/people/${personId}`, {method: 'PUT', body: JSON.stringify({birth_date: birthDate})}); await refresh(); showMessage(t('setup.birth_saved')); }
    catch (error) { showError(error); }
  }));
  ownerFields.replaceChildren(...people.map((person) => {
    const label = document.createElement('label');
    label.className = 'owner-field';
    label.innerHTML = `<input type="checkbox" data-person-id="${Number(person.id)}"> <span>${escapeHtml(person.name)}</span><input type="number" data-share-id="${Number(person.id)}" value="100" min="0.01" max="100" step="0.01">%`;
    return label;
  }));
}

function renderAccounts() {
  accountsList.replaceChildren(...accounts.map((account) => {
    const item = document.createElement('div');
    const values = editableAccountValues(account);
    item.className = 'account-row';
    item.innerHTML = `<label>${t('setup.institution')}<input data-account-field="institution" data-account-id="${Number(account.id)}"></label><label>${t('setup.name')}<input data-account-field="name" data-account-id="${Number(account.id)}"></label><label>${account.asset_kind === 'gic' ? t('setup.reference') : t('setup.account_number')}<input data-account-field="account_number" data-account-id="${Number(account.id)}" ${account.asset_kind === 'gic' ? '' : 'required'}></label><span>${escapeHtml(accountTypeLabel(account.account_type))} · ${escapeHtml(account.owners || t('setup.unassigned'))}</span><button type="button" data-save-account="${Number(account.id)}" hidden>${t('setup.save_changes')}</button>`;
    item.querySelectorAll('[data-account-field]').forEach((input) => {
      input.value = values[input.dataset.accountField];
      input.dataset.originalValue = values[input.dataset.accountField];
    });
    return item;
  }));
  accountsList.querySelectorAll('[data-account-field]').forEach((input) => input.addEventListener('input', () => {
    const button = accountsList.querySelector(`[data-save-account="${input.dataset.accountId}"]`);
    const fields = accountsList.querySelectorAll(`[data-account-id="${input.dataset.accountId}"]`);
    button.hidden = [...fields].every((field) => field.value === field.dataset.originalValue);
  }));
  accountsList.querySelectorAll('[data-save-account]').forEach((button) => button.addEventListener('click', async () => {
    const fields = accountsList.querySelectorAll(`[data-account-id="${button.dataset.saveAccount}"]`);
    const values = Object.fromEntries([...fields].map((field) => [field.dataset.accountField, field.value]));
    try { await api(`/api/model/accounts/${button.dataset.saveAccount}`, {method: 'PUT', body: JSON.stringify(values)}); await refresh(); showMessage(t('setup.account_saved')); }
    catch (error) { showError(error); }
  }));
  accountSelectors.forEach((select) => select.replaceChildren(...accounts.map((account) => new Option(`${accountLabel(account)} (${accountTypeLabel(account.account_type)})`, account.id))));
}

async function refresh() {
  people = (await api('/api/model/people')).people;
  accounts = (await api('/api/model/accounts')).accounts;
  renderPeople();
  renderAccounts();
}

document.querySelector('#person-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  try { await api('/api/model/people', {method: 'POST', body: JSON.stringify(Object.fromEntries(new FormData(event.target)))}); event.target.reset(); resetPersonFormState(); await refresh(); showMessage(t('setup.person_added')); }
  catch (error) { showError(error); }
});

document.querySelector('#account-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  try {
    const form = Object.fromEntries(new FormData(event.target));
    const owners = [...ownerFields.querySelectorAll('input[type="checkbox"]:checked')].map((check) => ({person_id: Number(check.dataset.personId), share: Number(ownerFields.querySelector(`[data-share-id="${check.dataset.personId}"]`).value) / 100}));
    await api('/api/model/accounts', {method: 'POST', body: JSON.stringify({...form, owners})});
    event.target.reset(); resetAccountFormState(); await refresh(); showMessage(t('setup.account_added'));
  } catch (error) { showError(error); }
});

document.querySelector('#balance-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  try { const form = Object.fromEntries(new FormData(event.target)); await api(`/api/model/accounts/${form.account_id}/balance`, {method: 'POST', body: JSON.stringify(form)}); resetBalanceFormState(); showMessage(t('setup.balance_saved')); }
  catch (error) { showError(error); }
});

document.querySelector('#gic-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  try { const form = Object.fromEntries(new FormData(event.target)); form.redeemable = event.target.redeemable.checked; await api(`/api/model/accounts/${form.account_id}/gics`, {method: 'POST', body: JSON.stringify(form)}); event.target.reset(); resetGicFormState(); showMessage(t('setup.gic_added')); }
  catch (error) { showError(error); }
});

document.querySelector('#scenario-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  try { await api('/api/model/scenarios', {method: 'POST', body: JSON.stringify(Object.fromEntries(new FormData(event.target)))}); resetScenarioFormState(); showMessage(t('setup.scenario_created')); }
  catch (error) { showError(error); }
});

refresh().catch(showError);
