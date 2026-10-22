// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {accountTypeLabel} from '../shared/account-types.mjs';
import {escapeHtml} from '../shared/html.mjs';
import {createLatestRequestGate} from './latest-request.mjs';
import {t, locale} from '../shared/i18n.mjs';
import {calendarDateSortKey, formatDate, formatMoneyDollars} from '../shared/locale-format.mjs';
import {importMessage} from './transaction-import-message.mjs';
import {importHistoryHtml, transactionsTableHtml} from './transactions-render.mjs';
import {createDialog} from '../shared/dialog.mjs';
import {initializeTableDensity} from '../shared/table-density.mjs';

const tabs = document.querySelectorAll('.view-tab');
const importDialog = document.querySelector('#import-dialog');
const importForm = document.querySelector('#transaction-import-form');
const importSubmit = document.querySelector('#import-submit-button');
const importResult = document.querySelector('#import-result');
const toast = document.querySelector('#toast');
const fileInputs = importForm.querySelectorAll('input[type="file"]');
const accountFilter = document.querySelector('#transaction-account-filter');
const reconciliationStatus = document.querySelector('#reconciliation-status');
const money = (value) => value == null ? '' : formatMoneyDollars(value);
const date = (value) => calendarDateSortKey(value)[0] ? formatDate(value) : value;
const reconcileButton = document.querySelector('#open-reconcile-button');
const reconcileDialog = document.querySelector('#reconcile-dialog');
const reconcileForm = document.querySelector('#reconcile-form');
const reconcileResult = document.querySelector('#reconcile-result');
const importTitle = document.querySelector('#import-dialog-title');
const importDescription = document.querySelector('#import-dialog-description');
const importDescriptionHtml = importDescription.innerHTML || escapeHtml(importDescription.dataset.defaultText || '');
const breadcrumbCategory = document.querySelector('#breadcrumb-category');
const breadcrumbAccount = document.querySelector('#breadcrumb-account');
const pageParams = new URLSearchParams(window.location.search);
const validTypes = ['non_registered', 'tfsa', 'rrsp', 'resp'];
let transactionType = validTypes.includes(pageParams.get('type')) ? pageParams.get('type') : 'non_registered';
let requestedAccountId = pageParams.get('account_id') || '';
const transactionsGate = createLatestRequestGate();
const historyGate = createLatestRequestGate();
const accountsGate = createLatestRequestGate();
const reconciliationGate = createLatestRequestGate();
const refreshGate = createLatestRequestGate();
const workspaceGate = createLatestRequestGate();
const importController = dialogController(importDialog);
const reconcileController = dialogController(reconcileDialog);
const confirmDialog = document.querySelector('#import-confirm-dialog');
const confirmController = dialogController(confirmDialog);
const importLabel = importSubmit.textContent;
const instructions = document.querySelector('#import-instructions');
function openInlineHelp() {
  instructions.open = true;
  instructions.querySelector('summary').focus();
}
document.querySelector('#import-inline-help').addEventListener('click', openInlineHelp);
let importBusy = false;
let reconcileBusy = false;
let answerConfirmation = null;

function dialogController(dialog) {
  const controller = createDialog(dialog);
  dialog.addEventListener('close', () => { if (!dialog.open) dialog.hidden = true; });
  return {
    open() { dialog.hidden = false; controller.open(); },
    close() { controller.close(); },
  };
}

function confirmImport(message, language = locale) {
  showResult(document.querySelector('#import-confirm-message'), message, false, language);
  confirmController.open();
  return new Promise(resolve => { answerConfirmation = resolve; });
}

document.querySelector('#import-confirm-continue').addEventListener('click', () => {
  const answer = answerConfirmation;
  answerConfirmation = null;
  confirmController.close();
  answer?.(true);
});
confirmDialog.addEventListener('close', () => {
  if (confirmDialog.open) return;
  const answer = answerConfirmation;
  answerConfirmation = null;
  answer?.(false);
});

function setImportBusy(busy) {
  importBusy = busy;
  importForm.setAttribute('aria-busy', String(busy));
  importSubmit.setAttribute('aria-busy', String(busy));
  importSubmit.textContent = busy ? t('transactions.importing') : importLabel;
  importDialog.querySelectorAll('input, select, button').forEach(control => { control.disabled = busy; });
  updateImportButton();
}
async function reportCancelledImport(data, key) {
  const processed = Number(data.files_imported || 0) > 0;
  showResult(importResult, processed ? t('transactions.processed_files') : t(key));
  if (processed) await refresh();
}
importDialog.addEventListener('cancel', event => { if (importBusy) event.preventDefault(); });
reconcileDialog.addEventListener('cancel', event => { if (reconcileBusy) event.preventDefault(); });
const density = document.querySelector('#transaction-density');
if (density) initializeTableDensity(density, document.querySelector('.fv-transactions'), 'foreview.transactions.table-density');

function accountLabel(account) {
  return account.asset_kind === 'gic'
    ? `${t('accounts.gic')} · ${account.name || t('transactions.unnamed')}`
    : `${account.account_number || ''} · ${account.institution || ''} ${account.name || ''}`;
}

function populateAccountSelect(select, accounts, includeAll = false) {
  select.replaceChildren();
  if (includeAll) select.add(new Option(t('transactions.all'), ''));
  const parents = accounts.filter((account) => !account.parent_account_id);
  parents.forEach((parent) => {
    select.add(new Option(accountLabel(parent), parent.id));
    const children = accounts.filter((account) => account.parent_account_id === parent.id);
    if (!children.length) return;
    const group = document.createElement('optgroup');
    group.label = t('transactions.linked', {account: accountLabel(parent)});
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
  breadcrumbCategory.textContent = accountTypeLabel(transactionType);
  const selected = accountFilter.selectedOptions[0];
  breadcrumbAccount.textContent = accountFilter.value && selected ? ` / ${selected.textContent}` : '';
}

function activateTab() {
  tabs.forEach((item) => {
    const active = item.dataset.type === transactionType;
    item.classList.toggle('active', active);
    item.setAttribute('aria-pressed', String(active));
  });
}

function selectedFiles() {
  return [...fileInputs].flatMap((input) => [...input.files]);
}

function updateImportButton() {
  importSubmit.disabled = importBusy || selectedFiles().length === 0;
  const review = document.querySelector('#import-file-review');
  review.replaceChildren(...selectedFiles().map(file => {
    const item = document.createElement('li');
    item.textContent = file.webkitRelativePath || file.name;
    return item;
  }));
  if (!review.children.length) {
    const item = document.createElement('li');
    item.textContent = t('transactions.no_files');
    review.append(item);
  }
}

function showResult(target, message, error = false, language = locale) {
  target.textContent = message;
  target.classList.toggle('error', error);
  target.lang = language;
  target.hidden = !message;
  target.setAttribute('role', error ? 'alert' : 'status');
}

function openImportDialog() {
  importForm.reset();
  showResult(importResult, '');
  importDescription.innerHTML = importDescriptionHtml;
  if (accountFilter.value) document.querySelector('#transaction-account').value = accountFilter.value;
  updateImportButton();
  importController.open();
}

function openReconcileDialog() {
  const selected = accountFilter.selectedOptions[0];
  reconcileForm.reset();
  showResult(reconcileResult, '');
  document.querySelector('#reconcile-account-label').value = selected ? selected.textContent : '';
  document.querySelector('#reconcile-date').value = new Date().toISOString().slice(0, 10);
  reconcileController.open();
}

function showToast(message) {
  toast.textContent = message;
  toast.hidden = false;
}

function styleTables(container, label) {
  container.querySelectorAll('table').forEach(table => {
    table.classList.add('fv-table');
    const caption = table.createCaption();
    caption.textContent = label;
    table.querySelectorAll('thead th').forEach(cell => {cell.scope = 'col';});
  });
  container.querySelectorAll('.table-card').forEach(region => {
    region.classList.add('fv-table-scroll');
    region.tabIndex = 0;
    region.setAttribute('role', 'region');
    region.setAttribute('aria-label', label);
    region.setAttribute('aria-describedby', 'transactions-scroll-hint');
  });
}

async function loadReconciliationStatus() {
  const isCurrent = reconciliationGate.begin();
  reconciliationStatus.hidden = true;
  if (!accountFilter.value) return;
  const response = await fetch(`/api/model/accounts/${accountFilter.value}/reconciliation`);
  if (!response.ok) throw new Error(t('transactions.load_reconciliation'));
  const data = await response.json();
  if (!isCurrent()) return;
  if (!data.reconciled_through) return;
  const review = data.checkpoints.filter((item) => item.status === 'needs_review');
  const latest = review[review.length - 1];
  reconciliationStatus.textContent = latest
    ? t('transactions.needs_review', {date: date(latest.reconciled_through), amount: money(latest.difference ?? 0)})
    : t('transactions.reconciled', {date: date(data.reconciled_through)});
  reconciliationStatus.classList.toggle('error', Boolean(latest));
  reconciliationStatus.hidden = false;
}

async function postImport(formData) {
  const response = await fetch('/api/model/transactions/import', {method: 'POST', body: formData});
  return {response, data: await responseJson(response)};
}

async function responseJson(response) {
  const body = await response.text();
  if (!body) {
    const error = new Error(t('transactions.empty_response', {status: response.status}));
    error.language = locale;
    throw error;
  }
  try {
    return JSON.parse(body);
  } catch {
    const error = new Error(body.slice(0, 500) || t('transactions.invalid_response', {status: response.status}));
    error.language = body ? 'en-CA' : locale;
    throw error;
  }
}

async function loadAccounts() {
  const isCurrent = accountsGate.begin();
  const response = await fetch('/api/model/accounts');
  if (!response.ok) throw new Error(t('transactions.load_accounts'));
  const { accounts } = await response.json();
  if (!isCurrent()) return false;
  const selectedId = requestedAccountId || accountFilter.value;
  const filteredAccounts = accounts.filter((account) => account.account_type === transactionType);
  populateAccountSelect(document.querySelector('#transaction-account'), filteredAccounts);
  document.querySelector('#transaction-account').insertBefore(new Option(t('transactions.auto'), 'auto'), document.querySelector('#transaction-account').firstChild);
  populateAccountSelect(accountFilter, filteredAccounts, true);
  if (selectedId && [...accountFilter.options].some((option) => option.value === selectedId)) {
    accountFilter.value = selectedId;
    document.querySelector('#transaction-account').value = selectedId;
    requestedAccountId = '';
  }
  updateBreadcrumb();
  return true;
}

async function loadTransactions() {
  const isCurrent = transactionsGate.begin();
  const container = document.querySelector('#transactions-table-content');
  container.setAttribute('aria-busy', 'true');
  try {
    const params = new URLSearchParams({account_type: transactionType});
    if (accountFilter.value) params.set('account_id', accountFilter.value);
    const query = `?${params.toString()}`;
    const response = await fetch(`/api/model/transactions${query}`);
    if (!response.ok) throw new Error(t('transactions.load_transactions'));
    const { transactions, opening_balances: openingBalances = [] } = await response.json();
    if (!isCurrent()) return;
    container.innerHTML = transactionsTableHtml(
      transactions,
      openingBalances,
      Boolean(accountFilter.value),
    );
    styleTables(container, t('transactions.table_label'));
  } catch (failure) {
    if (isCurrent()) container.textContent = failure.message;
    throw failure;
  } finally {
    if (isCurrent()) container.setAttribute('aria-busy', 'false');
  }
}

async function loadImportHistory() {
  const isCurrent = historyGate.begin();
  const container = document.querySelector('#import-history-content');
  container.setAttribute('aria-busy', 'true');
  try {
    const params = new URLSearchParams({account_type: transactionType});
    if (accountFilter.value) params.set('account_id', accountFilter.value);
    const response = await fetch(`/api/model/import-history?${params.toString()}`);
    if (!response.ok) throw new Error(t('transactions.load_history'));
    const { imports } = await response.json();
    if (!isCurrent()) return;
    container.innerHTML = importHistoryHtml(imports);
    styleTables(container, t('transactions.history_label'));
  } catch (failure) {
    if (isCurrent()) container.textContent = failure.message;
    throw failure;
  } finally {
    if (isCurrent()) container.setAttribute('aria-busy', 'false');
  }
}

function resetReadViews() {
  for (const id of ['transactions-table-content', 'import-history-content']) {
    const container = document.getElementById(id);
    container.textContent = t('transactions.loading');
    container.setAttribute('aria-busy', 'true');
  }
  reconciliationStatus.hidden = true;
}

async function refresh() {
  const isCurrent = refreshGate.begin();
  const error = document.querySelector('#transactions-error');
  const retry = document.querySelector('#transactions-retry');
  error.hidden = true;
  retry.hidden = true;
  resetReadViews();
  try {
    await Promise.all([loadTransactions(), loadImportHistory(), loadReconciliationStatus()]);
  } catch (failure) {
    if (!isCurrent()) return;
    showResult(error, failure.message, true);
    retry.hidden = false;
  }
}
async function loadWorkspace() {
  const isCurrent = workspaceGate.begin();
  transactionsGate.begin();
  historyGate.begin();
  reconciliationGate.begin();
  refreshGate.begin();
  resetReadViews();
  document.querySelector('#transactions-error').hidden = true;
  document.querySelector('#transactions-retry').hidden = true;
  accountFilter.disabled = true;
  document.querySelector('#open-import-button').disabled = true;
  reconcileButton.disabled = true;
  try {
    if (!await loadAccounts() || !isCurrent()) return;
    accountFilter.disabled = false;
    document.querySelector('#open-import-button').disabled = false;
    reconcileButton.disabled = !accountFilter.value;
    syncLocation();
    await refresh();
  } catch (error) {
    if (!isCurrent()) return;
    showResult(document.querySelector('#transactions-error'), error.message, true);
    document.querySelector('#transactions-retry').hidden = false;
    for (const id of ['transactions-table-content', 'import-history-content']) {
      const container = document.getElementById(id);
      container.textContent = error.message;
      container.setAttribute('aria-busy', 'false');
    }
  }
}
document.querySelector('#transactions-retry').addEventListener('click', loadWorkspace);

fileInputs.forEach((input) => input.addEventListener('change', updateImportButton));
tabs.forEach((tab) => tab.addEventListener('click', async () => {
  transactionType = tab.dataset.type;
  activateTab();
  requestedAccountId = '';
  accountFilter.value = '';
  reconcileButton.disabled = true;
  reconciliationStatus.hidden = true;
  syncLocation();
  updateBreadcrumb();
  await loadWorkspace();
}));
accountFilter.addEventListener('change', () => {
  reconcileButton.disabled = !accountFilter.value;
  document.querySelector('#transaction-account').value = accountFilter.value || 'auto';
  syncLocation();
  updateBreadcrumb();
  refresh();
});
document.querySelector('#open-import-button').addEventListener('click', openImportDialog);
reconcileButton.addEventListener('click', openReconcileDialog);

importForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (importBusy) return;
  const formData = new FormData(importForm);
  setImportBusy(true);
  showResult(importResult, t('transactions.importing'));
  try {
    let {response, data} = await postImport(formData);
    while (response.status === 409) {
      const creation = Boolean(data.confirm_account_creation);
      const flag = creation ? 'confirm_account_creation' : data.confirm_reconciled ? 'confirm_reconciled' : null;
      // Each permission can be granted once, in the order requested by this batch.
      if (!flag || formData.has(flag)) break;
      const proceed = await confirmImport(
        creation ? `${data.error || ''} ${t('transactions.create_confirm')}` : t('transactions.reconciled_confirm'),
        creation ? data.error_language || locale : locale,
      );
      if (!proceed) {
        await reportCancelledImport(data, creation ? 'transactions.create_cancelled' : 'transactions.reconciled_cancelled');
        updateImportButton();
        return;
      }
      formData.set(flag, '1');
      ({response, data} = await postImport(formData));
    }
    if (!response.ok) {
      const error = new Error(data.error);
      error.language = data.error_language || 'en-CA';
      error.helpUrl = data.help_url;
      throw error;
    }
    const flagged = (data.results || []).flatMap((item) => item.reconciled_periods_needing_review || []);
    const review = flagged.length ? ` ${t(flagged.length === 1 ? 'transactions.review_period' : 'transactions.review_periods', {count: flagged.length})}` : '';
    showToast(`${importMessage(data)}${review} ${t('transactions.duplicates', {count: data.duplicates || 0})}`);
    await refresh();
    importForm.reset();
    importController.close();
  } catch (error) {
    showResult(importResult, error.message, true, error.language || 'en-CA');
    if (error.helpUrl) {
      const link = document.createElement('a');
      link.href = '#transaction-import-help';
      link.textContent = t('transactions.open_help');
      link.addEventListener('click', (event) => {
        event.preventDefault();
        openInlineHelp();
      });
      importResult.append(link);
    }
    updateImportButton();
  } finally {
    setImportBusy(false);
    if (importDialog.open) importSubmit.focus();
  }
});

reconcileForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (reconcileBusy) return;
  reconcileBusy = true;
  const submit = document.querySelector('#reconcile-submit-button');
  const payload = {
    date: document.querySelector('#reconcile-date').value,
    amount: document.querySelector('#reconcile-amount').value,
  };
  reconcileDialog.querySelectorAll('input, button').forEach(control => {control.disabled = true;});
  submit.disabled = true;
  submit.setAttribute('aria-busy', 'true');
  showResult(reconcileResult, t('transactions.reconciling'));
  try {
    const response = await fetch(`/api/model/accounts/${accountFilter.value}/reconcile`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    const data = await responseJson(response);
    if (!response.ok) {
      const error = new Error(data.error);
      error.language = data.error_language || 'en-CA';
      throw error;
    }
    const difference = data.difference == null ? t('transactions.no_prior_balance') : t('transactions.balance_difference', {amount: money(data.difference)});
    const locked = data.reconciled_through ? ` ${t('transactions.reconciled', {date: date(data.reconciled_through)})}` : '';
    showToast(`${t('transactions.account_reconciled')} ${difference}${locked}`);
    await refresh();
    reconcileController.close();
  } catch (error) {
    showResult(reconcileResult, error.message, true, error.language || 'en-CA');
  } finally {
    reconcileBusy = false;
    reconcileDialog.querySelectorAll('input, button').forEach(control => {control.disabled = false;});
    submit.disabled = false;
    submit.setAttribute('aria-busy', 'false');
  }
});

activateTab();
loadWorkspace();
