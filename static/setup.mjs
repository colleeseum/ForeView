import {escapeHtml} from './html.mjs';
import {editableAccountValues} from './setup-values.mjs';

const message = document.querySelector('#setup-message');
const peopleList = document.querySelector('#people-list');
const accountsList = document.querySelector('#accounts-list');
const ownerFields = document.querySelector('#owner-fields');
const accountSelectors = [document.querySelector('#balance-account'), document.querySelector('#gic-account')];
function accountLabel(account) {
  if (account.asset_kind === 'gic') return `GIC · ${account.name || 'Unnamed'}`;
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

function showMessage(text, error = false) {
  message.textContent = text;
  message.className = `form-message${error ? ' error' : ''}`;
}

async function api(url, options = {}) {
  const response = await fetch(url, {headers: {'Content-Type': 'application/json'}, ...options});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Request failed');
  return data;
}

function renderPeople() {
  peopleList.replaceChildren(...people.map((person) => {
    const item = document.createElement('li');
    item.innerHTML = `<strong>${escapeHtml(person.name)}</strong><label class="inline-date">Birth date<input type="date" data-birth-date="${Number(person.id)}" data-original-date="${escapeHtml(person.birth_date)}" value="${escapeHtml(person.birth_date)}" required></label><button type="button" data-save-person="${Number(person.id)}" hidden>Save</button>`;
    return item;
  }));
  peopleList.querySelectorAll('[data-birth-date]').forEach((input) => input.addEventListener('input', () => {
    const saveButton = peopleList.querySelector(`[data-save-person="${input.dataset.birthDate}"]`);
    saveButton.hidden = input.value === input.dataset.originalDate;
  }));
  peopleList.querySelectorAll('[data-save-person]').forEach((button) => button.addEventListener('click', async () => {
    const personId = button.dataset.savePerson;
    const birthDate = peopleList.querySelector(`[data-birth-date="${personId}"]`).value;
    try { await api(`/api/model/people/${personId}`, {method: 'PUT', body: JSON.stringify({birth_date: birthDate})}); await refresh(); showMessage('Birth date saved.'); }
    catch (error) { showMessage(error.message, true); }
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
    item.innerHTML = `<label>Institution<input data-account-field="institution" data-account-id="${Number(account.id)}"></label><label>Name<input data-account-field="name" data-account-id="${Number(account.id)}"></label><label>${account.asset_kind === 'gic' ? 'Reference (optional)' : 'Account number'}<input data-account-field="account_number" data-account-id="${Number(account.id)}" ${account.asset_kind === 'gic' ? '' : 'required'}></label><span>${escapeHtml(account.account_type)} · ${escapeHtml(account.owners || 'ownership not assigned')}</span><button type="button" data-save-account="${Number(account.id)}" hidden>Save changes</button>`;
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
    try { await api(`/api/model/accounts/${button.dataset.saveAccount}`, {method: 'PUT', body: JSON.stringify(values)}); await refresh(); showMessage('Account changes saved.'); }
    catch (error) { showMessage(error.message, true); }
  }));
  accountSelectors.forEach((select) => select.replaceChildren(...accounts.map((account) => new Option(`${accountLabel(account)} (${account.account_type})`, account.id))));
}

async function refresh() {
  people = (await api('/api/model/people')).people;
  accounts = (await api('/api/model/accounts')).accounts;
  renderPeople();
  renderAccounts();
}

document.querySelector('#person-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  try { await api('/api/model/people', {method: 'POST', body: JSON.stringify(Object.fromEntries(new FormData(event.target)))}); event.target.reset(); resetPersonFormState(); await refresh(); showMessage('Person added.'); }
  catch (error) { showMessage(error.message, true); }
});

document.querySelector('#account-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  try {
    const form = Object.fromEntries(new FormData(event.target));
    const owners = [...ownerFields.querySelectorAll('input[type="checkbox"]:checked')].map((check) => ({person_id: Number(check.dataset.personId), share: Number(ownerFields.querySelector(`[data-share-id="${check.dataset.personId}"]`).value) / 100}));
    await api('/api/model/accounts', {method: 'POST', body: JSON.stringify({...form, owners})});
    event.target.reset(); resetAccountFormState(); await refresh(); showMessage('Account added.');
  } catch (error) { showMessage(error.message, true); }
});

document.querySelector('#balance-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  try { const form = Object.fromEntries(new FormData(event.target)); await api(`/api/model/accounts/${form.account_id}/balance`, {method: 'POST', body: JSON.stringify(form)}); resetBalanceFormState(); showMessage('Balance saved.'); }
  catch (error) { showMessage(error.message, true); }
});

document.querySelector('#gic-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  try { const form = Object.fromEntries(new FormData(event.target)); form.redeemable = event.target.redeemable.checked; await api(`/api/model/accounts/${form.account_id}/gics`, {method: 'POST', body: JSON.stringify(form)}); event.target.reset(); resetGicFormState(); showMessage('GIC added.'); }
  catch (error) { showMessage(error.message, true); }
});

document.querySelector('#scenario-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  try { await api('/api/model/scenarios', {method: 'POST', body: JSON.stringify(Object.fromEntries(new FormData(event.target)))}); resetScenarioFormState(); showMessage('Scenario created.'); }
  catch (error) { showMessage(error.message, true); }
});

refresh().catch((error) => showMessage(error.message, true));
