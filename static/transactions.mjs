// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {createLatestRequestGate} from './latest-request.mjs';
import {importMessage} from './transaction-import-message.mjs';
import {importHistoryHtml, transactionsTableHtml} from './transactions-render.mjs';

const tabs = document.querySelectorAll('.view-tab');
const importDialog = document.querySelector('#import-dialog');
const importForm = document.querySelector('#transaction-import-form');
const importSubmit = document.querySelector('#import-submit-button');
const importResult = document.querySelector('#import-result');
const toast = document.querySelector('#toast');
const fileInputs = importForm.querySelectorAll('input[type="file"]');
const accountFilter = document.querySelector('#transaction-account-filter');
const reconciliationStatus = document.querySelector('#reconciliation-status');
const money = (value) => value == null ? '' : Number(value).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
const reconcileButton = document.querySelector('#open-reconcile-button');
const reconcileDialog = document.querySelector('#reconcile-dialog');
const reconcileForm = document.querySelector('#reconcile-form');
const reconcileResult = document.querySelector('#reconcile-result');
const importTitle = document.querySelector('#import-dialog-title');
const importDescription = document.querySelector('#import-dialog-description');
const breadcrumbCategory = document.querySelector('#breadcrumb-category');
const breadcrumbAccount = document.querySelector('#breadcrumb-account');
const pageParams = new URLSearchParams(window.location.search);
const validTypes = ['non_registered', 'tfsa', 'rrsp', 'resp'];
let transactionType = validTypes.includes(pageParams.get('type')) ? pageParams.get('type') : 'non_registered';
let requestedAccountId = pageParams.get('account_id') || '';
const transactionsGate = createLatestRequestGate();
const historyGate = createLatestRequestGate();

const typeLabels = {non_registered: 'Non-registered', tfsa: 'TFSA', rrsp: 'RRSP', resp: 'RESP'};

function accountLabel(account) {
  return account.asset_kind === 'gic'
    ? `GIC · ${account.name || 'Unnamed'}`
    : `${account.account_number || ''} · ${account.institution || ''} ${account.name || ''}`;
}

function populateAccountSelect(select, accounts, includeAll = false) {
  select.replaceChildren();
  if (includeAll) select.add(new Option('All', ''));
  const parents = accounts.filter((account) => !account.parent_account_id);
  parents.forEach((parent) => {
    select.add(new Option(accountLabel(parent), parent.id));
    const children = accounts.filter((account) => account.parent_account_id === parent.id);
    if (!children.length) return;
    const group = document.createElement('optgroup');
    group.label = `Linked to ${accountLabel(parent)}`;
    children.forEach((child) => group.appendChild(new Option(`↳ ${accountLabel(child)}`, child.id)));
    select.appendChild(group);
  });
}

function syncLocation() {
  const params = new URLSearchParams({type: transactionType});
  if (accountFilter.value) params.set('account_id', accountFilter.value);
  const query = params.toString();
  window.history.replaceState({}, '', `${window.location.pathname}${query ? `?${query}` : ''}`);
}

function updateBreadcrumb() {
  breadcrumbCategory.textContent = typeLabels[transactionType];
  const selected = accountFilter.selectedOptions[0];
  breadcrumbAccount.textContent = accountFilter.value && selected ? ` / ${selected.textContent}` : '';
}

function activateTab() {
  tabs.forEach((item) => item.classList.toggle('active', item.dataset.type === transactionType));
}

function selectedFiles() {
  return [...fileInputs].flatMap((input) => [...input.files]);
}

function updateImportButton() {
  importSubmit.disabled = selectedFiles().length === 0;
}

function openImportDialog() {
  importForm.reset();
  importResult.textContent = '';
  importResult.classList.remove('error');
  importDescription.textContent = importDescription.dataset.defaultText;
  if (accountFilter.value) document.querySelector('#transaction-account').value = accountFilter.value;
  updateImportButton();
  importDialog.hidden = false;
}

function openReconcileDialog() {
  const selected = accountFilter.selectedOptions[0];
  reconcileForm.reset();
  reconcileResult.textContent = '';
  reconcileResult.classList.remove('error');
  document.querySelector('#reconcile-account-label').value = selected ? selected.textContent : '';
  document.querySelector('#reconcile-date').value = new Date().toISOString().slice(0, 10);
  reconcileDialog.hidden = false;
}

function showToast(message) {
  toast.textContent = message;
  toast.hidden = false;
  window.clearTimeout(showToast.timeout);
  showToast.timeout = window.setTimeout(() => { toast.hidden = true; }, 5000);
}

async function loadReconciliationStatus() {
  reconciliationStatus.hidden = true;
  if (!accountFilter.value) return;
  const response = await fetch(`/api/model/accounts/${accountFilter.value}/reconciliation`);
  if (!response.ok) return;
  const data = await response.json();
  if (!data.reconciled_through) return;
  const review = data.checkpoints.filter((item) => item.status === 'needs_review');
  const latest = review[review.length - 1];
  reconciliationStatus.textContent = latest
    ? `Needs review: the period reconciled through ${latest.reconciled_through} changed by $${Number(latest.difference || 0).toFixed(2)} after an import. Reconcile it again to confirm.`
    : `Reconciled through ${data.reconciled_through}.`;
  reconciliationStatus.classList.toggle('error', Boolean(latest));
  reconciliationStatus.hidden = false;
}

async function postImport(formData) {
  const response = await fetch('/api/model/transactions/import', {method: 'POST', body: formData});
  return {response, data: await responseJson(response)};
}

async function responseJson(response) {
  const body = await response.text();
  if (!body) throw new Error(`Server returned an empty response (${response.status}).`);
  try {
    return JSON.parse(body);
  } catch {
    throw new Error(body.slice(0, 500) || `Server returned an invalid response (${response.status}).`);
  }
}

async function loadAccounts() {
  const response = await fetch('/api/model/accounts');
  if (!response.ok) throw new Error('Could not load accounts.');
  const { accounts } = await response.json();
  const filteredAccounts = accounts.filter((account) => account.account_type === transactionType);
  populateAccountSelect(document.querySelector('#transaction-account'), filteredAccounts);
  document.querySelector('#transaction-account').insertBefore(new Option('Auto-detect from PDF', 'auto'), document.querySelector('#transaction-account').firstChild);
  populateAccountSelect(accountFilter, filteredAccounts, true);
  if (requestedAccountId && [...accountFilter.options].some((option) => option.value === requestedAccountId)) {
    accountFilter.value = requestedAccountId;
    document.querySelector('#transaction-account').value = requestedAccountId;
    requestedAccountId = '';
  }
  updateBreadcrumb();
}

async function loadTransactions() {
  const isCurrent = transactionsGate.begin();
  const params = new URLSearchParams({account_type: transactionType});
  if (accountFilter.value) params.set('account_id', accountFilter.value);
  const query = `?${params.toString()}`;
  const response = await fetch(`/api/model/transactions${query}`);
  if (!response.ok) throw new Error('Could not refresh transactions.');
  const { transactions, opening_balances: openingBalances = [] } = await response.json();
  if (!isCurrent()) return;
  document.querySelector('#transactions-table-content').innerHTML = transactionsTableHtml(
    transactions,
    openingBalances,
    Boolean(accountFilter.value),
  );
}

async function loadImportHistory() {
  const isCurrent = historyGate.begin();
  const params = new URLSearchParams({account_type: transactionType});
  if (accountFilter.value) params.set('account_id', accountFilter.value);
  const response = await fetch(`/api/model/import-history?${params.toString()}`);
  if (!response.ok) throw new Error('Could not load import history.');
  const { imports } = await response.json();
  if (!isCurrent()) return;
  document.querySelector('#import-history-content').innerHTML = importHistoryHtml(imports);
}

fileInputs.forEach((input) => input.addEventListener('change', updateImportButton));
tabs.forEach((tab) => tab.addEventListener('click', async () => {
  transactionType = tab.dataset.type;
  tabs.forEach((item) => item.classList.toggle('active', item === tab));
  requestedAccountId = '';
  accountFilter.value = '';
  reconcileButton.disabled = true;
  reconciliationStatus.hidden = true;
  syncLocation();
  updateBreadcrumb();
  await loadAccounts();
  await Promise.all([loadTransactions(), loadImportHistory()]);
}));
accountFilter.addEventListener('change', () => {
  reconcileButton.disabled = !accountFilter.value;
  loadReconciliationStatus();
  document.querySelector('#transaction-account').value = accountFilter.value || 'auto';
  syncLocation();
  updateBreadcrumb();
  Promise.all([loadTransactions(), loadImportHistory()]);
});
document.querySelector('#open-import-button').addEventListener('click', openImportDialog);
reconcileButton.addEventListener('click', openReconcileDialog);
document.querySelector('#close-import-dialog').addEventListener('click', () => { importDialog.hidden = true; });
document.querySelector('#close-reconcile-dialog').addEventListener('click', () => { reconcileDialog.hidden = true; });
importDialog.addEventListener('click', (event) => { if (event.target === importDialog) importDialog.hidden = true; });

importForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  importSubmit.disabled = true;
  try {
    const formData = new FormData(importForm);
    let {response, data} = await postImport(formData);
    if (response.status === 409 && data.confirm_account_creation) {
      const account = data.account;
      const proceed = window.confirm(
        `${data.error}\n\nCreate this account and continue importing?`
      );
      if (!proceed) {
        importResult.textContent = 'Import cancelled. No account or transactions were added.';
        importResult.classList.remove('error');
        updateImportButton();
        return;
      }
      formData.set('confirm_account_creation', '1');
      ({response, data} = await postImport(formData));
    }
    if (response.status === 409 && data.confirm_reconciled) {
      const proceed = window.confirm(`${data.error}\n\nImport anyway? The reconciled period will be checked again and flagged for review if it no longer matches.`);
      if (!proceed) {
        importResult.textContent = 'Import cancelled. Nothing was added to the reconciled period.';
        importResult.classList.remove('error');
        updateImportButton();
        return;
      }
      formData.set('confirm_reconciled', '1');
      ({response, data} = await postImport(formData));
    }
    if (!response.ok) {
      const error = new Error(data.error);
      error.helpUrl = data.help_url;
      throw error;
    }
    await loadTransactions();
    await loadImportHistory();
    importForm.reset();
    importDialog.hidden = true;
    const flagged = (data.results || []).flatMap((item) => item.reconciled_periods_needing_review || []);
    const review = flagged.length ? ` ${flagged.length} reconciled period${flagged.length === 1 ? ' needs' : 's need'} review.` : '';
    showToast(`${importMessage(data)}${review}`);
    await loadReconciliationStatus();
  } catch (error) {
    importResult.textContent = '';
    importResult.append(error.message);
    if (error.helpUrl) {
      const link = document.createElement('a');
      link.href = '#transaction-import-help';
      link.textContent = ' Open help';
      link.addEventListener('click', (event) => {
        event.preventDefault();
        if (window.openContextHelp) window.openContextHelp('transaction-import');
      });
      importResult.append(link);
    }
    importResult.classList.add('error');
    updateImportButton();
  }
});

reconcileForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const submit = document.querySelector('#reconcile-submit-button');
  submit.disabled = true;
  try {
    const response = await fetch(`/api/model/accounts/${accountFilter.value}/reconcile`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        date: document.querySelector('#reconcile-date').value,
        amount: document.querySelector('#reconcile-amount').value,
      }),
    });
    const data = await responseJson(response);
    if (!response.ok) throw new Error(data.error);
    await loadTransactions();
    reconcileDialog.hidden = true;
    const difference = data.difference == null ? 'No prior balance was available for comparison.' : `Difference from the prior calculated balance: ${money(data.difference)}.`;
    const locked = data.reconciled_through ? ` Reconciled through ${data.reconciled_through}.` : '';
    showToast(`Account reconciled. ${difference}${locked}`);
    await loadReconciliationStatus();
  } catch (error) {
    reconcileResult.textContent = error.message;
    reconcileResult.classList.add('error');
  } finally {
    submit.disabled = false;
  }
});

activateTab();
(async () => {
  await loadAccounts();
  reconcileButton.disabled = !accountFilter.value;
  syncLocation();
  await Promise.all([loadTransactions(), loadImportHistory(), loadReconciliationStatus()]);
})();
