// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {formatMoneyDollars, formatDisplayDate} from '../shared/locale-format.mjs';

import {t, locale} from '../shared/i18n.mjs';
import {initializeIconActions} from '../shared/icon-actions.mjs';
import {createDialog} from '../shared/dialog.mjs';

initializeIconActions();

const expenseDialog = document.querySelector('#expense-dialog-backdrop');
const categoryDialog = document.querySelector('#category-dialog-backdrop');
const categoryEditor = document.querySelector('#category-editor-backdrop');
const categoryForm = document.querySelector('#category-editor-form');
const categoryTitle = document.querySelector('#category-editor-title');
const categoryStatus = document.querySelector('#category-status-field');
const categorySave = document.querySelector('#category-editor-save');
const expenseYearSelect = document.querySelector('#expense-year-select');
const dialogs = new Map();
for (const dialog of document.querySelectorAll('.fv-expenses dialog')) initializeDialog(dialog);

function initializeDialog(dialog) {
  const controller = createDialog(dialog, {fallbackFocus: document.querySelector('#expense-categories')});
  const state = {controller, busy: false, controls: []};
  dialogs.set(dialog, state);
  dialog.addEventListener('close', () => {if (!dialog.open) dialog.hidden = true;});
  dialog.addEventListener('cancel', event => {if (state.busy) event.preventDefault();});
}

function setDialogBusy(dialog, busy) {
  const state = dialogs.get(dialog);
  if (state.busy === busy) return;
  state.busy = busy;
  dialog.setAttribute('aria-busy', String(busy));
  if (busy) {
    state.controls = [...dialog.querySelectorAll('input, select, textarea, button')].map(node => [node, node.disabled]);
    state.controls.forEach(([node]) => {node.disabled = true;});
  } else {
    state.controls.forEach(([node, disabled]) => {node.disabled = disabled;});
    state.controls = [];
  }
}

document.querySelectorAll('.fv-expenses button').forEach(node => node.classList.add('fv-button'));
document.querySelectorAll('.fv-expenses input, .fv-expenses select').forEach(node => node.classList.add('fv-input'));
document.querySelectorAll('.fv-expenses button[type="submit"], .fv-expenses .primary-button').forEach(node => node.classList.add('fv-button--primary'));
function enhanceExpenseTables(root = document) {
root.querySelectorAll('.table-card').forEach(region => {
  region.classList.add('fv-table-scroll');
  region.tabIndex = 0;
  region.setAttribute('role', 'region');
  region.setAttribute('aria-label', t('expenses.table_label'));
  region.setAttribute('aria-describedby', 'expense-scroll-hint');
  const table = region.querySelector('table');
  table.classList.add('fv-table');
  table.createCaption().textContent = t('expenses.table_label');
  table.querySelectorAll('thead th').forEach(node => {node.scope = 'col';});
});
}
enhanceExpenseTables(document.querySelector('.fv-expenses') || document);

expenseYearSelect?.addEventListener('change', () => expenseYearSelect.form?.requestSubmit());

export function importCompletionUrl(savedCount, savedYears, selectedYear, origin) {
  const nextUrl = new URL('/expenses', origin);
  nextUrl.searchParams.set('year', String(selectedYear));
  nextUrl.searchParams.set('imported', String(savedCount));
  nextUrl.searchParams.set('imported_years', [...savedYears].sort((left, right) => left - right).join(','));
  return nextUrl;
}

function openDialog(dialog) {
  if (!dialogs.has(dialog)) initializeDialog(dialog);
  dialog.hidden = false;
  dialogs.get(dialog).controller.open();
}

function closeDialog(dialog) {
  if (dialogs.get(dialog)?.busy) return;
  dialogs.get(dialog)?.controller.close();
}

function openCategoryEditor(button = null) {
  categoryEditor.querySelector('[data-form-message]')?.remove();
  categoryForm.reset();
  if (button) {
    categoryForm.action = button.dataset.action;
    categoryForm.elements.name.value = button.dataset.name;
    categoryForm.elements.classification.value = button.dataset.classification;
    categoryForm.elements.active.value = button.dataset.active;
    categoryTitle.textContent = categoryTitle.dataset.editText || t('expenses.edit_category');
    categorySave.textContent = categorySave.dataset.saveText || t('expenses.save_category');
    categoryStatus.hidden = false;
  } else {
    categoryForm.action = categoryForm.dataset.createAction;
    categoryTitle.textContent = categoryTitle.dataset.addText || t('expenses.add_category');
    categorySave.textContent = categorySave.dataset.createText || t('expenses.create_category');
    categoryStatus.hidden = true;
  }
  closeDialog(categoryDialog);
  openDialog(categoryEditor);
}

function returnToCategories() {
  closeDialog(categoryEditor);
  openDialog(categoryDialog);
}

const manualForm = expenseDialog.querySelector('form');
const manualTitle = document.querySelector('#expense-dialog-title');
const manualAddTitle = manualTitle?.textContent;
function prepareManualCategories(categoryId = null) {
  if (!manualForm) return;
  const select = manualForm.elements.category_id;
  for (const option of select.options) {
    const unavailable = option.dataset.archived === 'true' && option.value !== String(categoryId);
    option.disabled = unavailable;
    option.hidden = unavailable;
  }
  manualForm.hidden = ![...select.options].some(option => !option.disabled);
  if (categoryId === null) select.value = [...select.options].find(option => !option.disabled)?.value || '';
  expenseDialog.querySelector('[data-category-required]')?.toggleAttribute('hidden', !manualForm.hidden);
}
document.querySelector('#expense-add').addEventListener('click', () => {
  manualForm?.reset();
  prepareManualCategories();
  if (manualForm) delete manualForm.dataset.expenseId;
  if (manualTitle) manualTitle.textContent = manualAddTitle;
  expenseDialog.querySelector('[data-form-message]')?.remove();
  openDialog(expenseDialog);
});
document.addEventListener('click', event => {
  const button = event.target.closest('[data-expense-edit]');
  if (!button) return;
  const record = JSON.parse(button.dataset.expenseEdit);
  manualForm.reset();
  prepareManualCategories(record.category_id);
  for (const [field, value] of Object.entries(record)) {
    if (manualForm.elements[field]) manualForm.elements[field].value = value;
  }
  manualForm.dataset.expenseId = record.id;
  manualTitle.textContent = t('expenses.edit_expense');
  expenseDialog.querySelector('[data-form-message]')?.remove();
  openDialog(expenseDialog);
});
document.querySelector('#expense-categories').addEventListener('click', () => openDialog(categoryDialog));
document.querySelector('#expense-dialog-close').addEventListener('click', () => closeDialog(expenseDialog));
document.querySelector('#expense-dialog-cancel').addEventListener('click', () => closeDialog(expenseDialog));
document.querySelector('#category-dialog-close').addEventListener('click', () => closeDialog(categoryDialog));
document.querySelector('#category-add').addEventListener('click', () => openCategoryEditor());
document.querySelectorAll('[data-category-edit]').forEach((button) => {
  button.addEventListener('click', () => openCategoryEditor(button));
});
document.querySelector('#category-editor-close').addEventListener('click', returnToCategories);
document.querySelector('#category-editor-cancel').addEventListener('click', returnToCategories);
document.querySelector('#expense-open-categories').addEventListener('click', () => {
  closeDialog(expenseDialog);
  openDialog(categoryDialog);
});

categoryEditor.addEventListener('cancel', event => {
  event.preventDefault();
  if (!dialogs.get(categoryEditor)?.busy) returnToCategories();
});

async function responseJson(response) {
  let result;
  try {result = await response.json();}
  catch {
    const error = new Error(t('expenses.request_failed_status', {status: response.status}));
    error.language = locale;
    throw error;
  }
  if (!response.ok) {
    const error = new Error(result?.error || t('expenses.request_failed_status', {status: response.status}));
    error.language = result?.error ? result.error_language || 'en-CA' : locale;
    throw error;
  }
  return result;
}

export function expenseResultYear(record, selectedYear) {
  const start = Number(record?.period_start?.slice(0, 4));
  const end = Number(record?.period_end?.slice(0, 4));
  return start && end && (Number(selectedYear) < start || Number(selectedYear) > end) ? end : selectedYear;
}

// Existing JSON endpoints permit in-modal validation; ordinary form actions remain fallback.
for (const [dialog, form, category] of [[categoryEditor, categoryForm, true], [expenseDialog, expenseDialog.querySelector('form'), false]]) {
  form?.addEventListener('submit', async event => {
    event.preventDefault();
    if (dialogs.get(dialog)?.busy) return;
    const payload = new FormData(form);
    setDialogBusy(dialog, true);
    let message = dialog.querySelector('[data-form-message]');
    if (!message) {
      message = document.createElement('p');
      message.dataset.formMessage = '';
      message.className = 'fv-feedback';
      dialog.append(message);
    }
    message.textContent = t('expenses.saving');
    message.lang = locale;
    message.setAttribute('role', 'status');
    message.classList.remove('error');
    let result;
    try {
      const endpoint = category ? new URL(form.action).pathname.replace('/expenses/', '/api/expenses/')
        : form.dataset.expenseId ? `/api/expenses/${form.dataset.expenseId}` : '/api/expenses/manual';
      const method = /\/\d+$/.test(endpoint) ? 'PUT' : 'POST';
      result = await responseJson(await fetch(endpoint, {method, body: payload}));
    } catch (error) {
      message.textContent = error.message;
      message.lang = error.language || locale;
      message.setAttribute('role', 'alert');
      message.classList.add('error');
      setDialogBusy(dialog, false);
      return;
    }
    const target = new URL('/expenses', window.location.origin);
    const selectedYear = payload.get('year') || expenseYearSelect?.value || String(new Date().getFullYear());
    target.searchParams.set('year', category ? selectedYear : expenseResultYear(result, selectedYear));
    target.searchParams.set('message', t('expenses.saved'));
    if (category) target.searchParams.set('dialog', 'categories');
    message.textContent = t('expenses.saved');
    const retry = document.createElement('a');
    retry.href = target.href;
    retry.textContent = t('expenses.view_saved');
    message.append(' ', retry);
    window.location.assign(target);
  });
}
if (!categoryDialog.hidden) {
  // Promote server-rendered, non-modal fallback content to the modal top layer.
  categoryDialog.removeAttribute('open');
  openDialog(categoryDialog);
}

function initializeExpenseImport() {
  const dialog = document.querySelector('#expense-import-dialog-backdrop');
  const openButton = document.querySelector('#expense-import');
  if (!dialog || !openButton) return;
  if (!dialogs.has(dialog)) initializeDialog(dialog);
  const form = document.querySelector('#expense-import-form');
  form?.addEventListener('submit', event => event.preventDefault());
  const fileInput = document.querySelector('#expense-import-file');
  const previewButton = document.querySelector('#import-preview-btn');
  const confirmButton = document.querySelector('#import-confirm');
  const fileStep = document.querySelector('#import-step-file');
  const previewStep = document.querySelector('#import-step-preview');
  const progress = document.querySelector('#expense-import-progress');
  const progressText = progress?.querySelector('span');
  const queueStatus = document.querySelector('#expense-import-queue-status');
  const message = document.querySelector('#expense-import-message');
  const provider = document.querySelector('#import-provider');
  const providerKey = document.querySelector('#import-provider-key');
  const amount = document.querySelector('#import-amount');
  const periodStart = document.querySelector('#import-period-start');
  const periodEnd = document.querySelector('#import-period-end');
  const name = document.querySelector('#import-name');
  const category = document.querySelector('#import-category');
  const association = document.querySelector('#import-association');
  let pendingFiles = [];
  let currentFileIndex = 0;
  let savedCount = 0;
  let savedYears = new Set();
  let replacingFailedFile = false;

  function currentFile() {
    return pendingFiles[currentFileIndex] ?? null;
  }

  function updateQueueStatus() {
    if (!queueStatus) return;
    const file = currentFile();
    queueStatus.hidden = pendingFiles.length < 2 || !file;
    queueStatus.textContent = file
      ? `${savedCount ? `${t('expenses.saved_count', {count: savedCount})} ` : ''}${t('expenses.statement_progress', {current: currentFileIndex + 1, total: pendingFiles.length, name: file.name})}`
      : '';
  }

  function showError(error) {
    if (!message) return;
    message.textContent = error instanceof Error ? error.message : String(error);
    message.lang = error?.language || 'en-CA';
    message.hidden = false;
  }

  function clearError() {
    if (!message) return;
    message.textContent = '';
    message.lang = locale;
    message.hidden = true;
  }

  function setBusy(busy, label = progressText?.dataset.analysingText || t('expenses.analysing')) {
    setDialogBusy(dialog, busy);
    if (progress) progress.hidden = !busy;
    if (progressText) progressText.textContent = label;
    if (previewButton) previewButton.disabled = busy || !currentFile();
    if (confirmButton) confirmButton.disabled = busy;
  }

  function reset() {
    pendingFiles = [];
    currentFileIndex = 0;
    savedCount = 0;
    savedYears = new Set();
    replacingFailedFile = false;
    form?.reset();
    document.querySelector('#expense-file-review')?.replaceChildren();
    clearError();
    if (fileStep) fileStep.hidden = false;
    if (previewStep) previewStep.hidden = true;
    if (confirmButton) confirmButton.hidden = true;
    if (previewButton) previewButton.hidden = false;
    updateQueueStatus();
    setBusy(false);
  }

  function dismiss() {
    if (dialogs.get(dialog).busy) return;
    closeDialog(dialog);
    if (savedCount) {
      window.location.assign(importCompletionUrl(savedCount, savedYears, expenseYearSelect?.value || [...savedYears].at(-1), window.location.origin));
      return;
    }
    reset();
  }

  openButton.addEventListener('click', () => {
    reset();
    openDialog(dialog);
  });
  document.querySelector('#expense-import-close')?.addEventListener('click', dismiss);
  document.querySelector('#import-cancel')?.addEventListener('click', dismiss);
  document.querySelector('#import-open-categories')?.addEventListener('click', () => {
    closeDialog(dialog);
    openCategoryEditor();
  });

  fileInput?.addEventListener('change', () => {
    if (dialogs.get(dialog).busy) return;
    const selectedFiles = Array.from(fileInput.files ?? []);
    if (replacingFailedFile) {
      pendingFiles = [
        ...pendingFiles.slice(0, currentFileIndex),
        ...selectedFiles,
        ...pendingFiles.slice(currentFileIndex + 1),
      ];
      replacingFailedFile = false;
    } else {
      pendingFiles = selectedFiles;
      currentFileIndex = 0;
      savedCount = 0;
      savedYears = new Set();
    }
    clearError();
    updateQueueStatus();
    const review = document.querySelector('#expense-file-review');
    review?.replaceChildren(...pendingFiles.map(file => {
      const item = document.createElement('li');
      item.textContent = file.name;
      return item;
    }));
    if (previewButton) previewButton.disabled = !currentFile();
  });

  async function previewCurrentFile() {
    if (dialogs.get(dialog).busy) return;
    const file = currentFile();
    if (!file) return;
    clearError();
    updateQueueStatus();
    setBusy(true);
    try {
      const payload = new FormData();
      payload.append('file', file, file.name);
      const response = await fetch('/api/expenses/import/preview', {
        method: 'POST',
        body: payload,
      });
      const {preview} = await responseJson(response);
      provider.textContent = preview.provider_display_name;
      provider.lang = preview.provider_display_language || 'en-CA';
      providerKey.value = preview.provider_key;
      amount.textContent = formatMoneyDollars(preview.amount);
      periodStart.textContent = formatDisplayDate(preview.period_start);
      periodEnd.textContent = formatDisplayDate(preview.period_end);
      name.value = preview.suggested_identity;
      association.value = 'household';
      fileStep.hidden = true;
      previewStep.hidden = false;
      confirmButton.hidden = false;
      previewButton.hidden = true;
      replacingFailedFile = false;
      previewStep.tabIndex = -1;
      previewStep.focus();
    } catch (error) {
      replacingFailedFile = true;
      if (fileStep) fileStep.hidden = false;
      if (previewStep) previewStep.hidden = true;
      if (confirmButton) confirmButton.hidden = true;
      if (previewButton) previewButton.hidden = false;
      showError(error);
    } finally {
      setBusy(false);
    }
  }

  previewButton?.addEventListener('click', async () => {
    await previewCurrentFile();
  });

  confirmButton?.addEventListener('click', async () => {
    if (dialogs.get(dialog).busy) return;
    const file = currentFile();
    if (!file || !name || !category || !providerKey) return;
    if (!name.reportValidity() || !category.reportValidity()) return;
    clearError();
    setBusy(true, progressText?.dataset.savingText || t('expenses.saving'));
    let completion;
    try {
      const payload = new FormData();
      payload.append('file', file, file.name);
      payload.append('provider_key', providerKey.value);
      payload.append('name', name.value);
      payload.append('category_id', category.value);
      payload.append('association', association?.value || 'household');
      const response = await fetch('/api/expenses/import/confirm', {
        method: 'POST',
        body: payload,
      });
      const confirmed = await responseJson(response);
      savedCount += 1;
      const startYear = Number(confirmed.period_start.slice(0, 4));
      const endYear = Number(confirmed.period_end.slice(0, 4));
      for (let year = startYear; year <= endYear; year += 1) savedYears.add(year);
      if (currentFileIndex + 1 < pendingFiles.length) {
        currentFileIndex += 1;
        previewStep.hidden = true;
        confirmButton.hidden = true;
        setBusy(false);
        await previewCurrentFile();
        return;
      }
      completion = importCompletionUrl(
        savedCount,
        savedYears,
        confirmed.period_end.slice(0, 4),
        window.location.origin,
      );
    } catch (error) {
      showError(error);
      setBusy(false);
      return;
    }
    // The write is committed. A navigation problem must not enable its POST again.
    const link = document.createElement('a');
    link.href = completion.href;
    link.textContent = t('expenses.view_saved');
    message.replaceChildren(document.createTextNode(`${t('expenses.saved_count', {count: savedCount})} `), link);
    message.classList.remove('error');
    message.setAttribute('role', 'status');
    message.hidden = false;
    window.location.assign(completion);
  });

  dialog.addEventListener('cancel', event => {
    event.preventDefault();
    dismiss();
  });
}

initializeExpenseImport();

function initializeExpenseDeletion() {
  const dialog = document.querySelector('#expense-delete-dialog');
  if (!dialog) return;
  const details = dialog.querySelector('#expense-delete-details');
  const message = dialog.querySelector('#expense-delete-message');
  const confirm = dialog.querySelector('#expense-delete-confirm');
  const retry = dialog.querySelector('#expense-delete-refresh');
  const records = document.querySelector('#expense-records');
  const summary = document.querySelector('#expense-summary');
  const feedback = document.querySelector('#expense-record-feedback');
  let selected = null;
  let uncertain = false;
  let focusTarget = null;
  let scrollPosition;
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-expense-delete]');
    if (!button || uncertain || dialogs.get(dialog).busy) return;
    selected = JSON.parse(button.dataset.expenseDelete);
    const row = button.closest('[data-expense-id]');
    focusTarget = row?.nextElementSibling?.querySelector('button, input') || row?.previousElementSibling?.querySelector('button, input') || document.querySelector('.expense-record-details summary');
    scrollPosition = {left: window.scrollX, top: window.scrollY};
    details.textContent = [selected.name, selected.source_name, formatMoneyDollars(selected.amount),
      `${formatDisplayDate(selected.period_start)} – ${formatDisplayDate(selected.period_end)}`].filter(Boolean).join(' · ');
    message.hidden = true;
    message.classList.remove('error');
    confirm.hidden = false;
    retry.hidden = true;
    openDialog(dialog);
  });
  function dismiss() {
    if (dialogs.get(dialog).busy) return;
    closeDialog(dialog);
    if (!selected) {
      (focusTarget?.isConnected ? focusTarget : document.querySelector('.expense-record-details summary'))?.focus({preventScroll: true});
      window.scrollTo(scrollPosition);
    }
  }
  for (const id of ['expense-delete-cancel', 'expense-delete-close']) {
    dialog.querySelector(`#${id}`).addEventListener('click', dismiss);
  }
  dialog.addEventListener('cancel', event => {
    if (!selected) {event.preventDefault(); dismiss();}
  });
  async function refresh() {
    if (!dialog.open) scrollPosition = {left: window.scrollX, top: window.scrollY};
    setDialogBusy(dialog, true);
    try {
      const url = new URL('/expenses', window.location.origin);
      url.searchParams.set('year', expenseYearSelect?.value || String(new Date().getFullYear()));
      const response = await fetch(url, {cache: 'no-store'});
      if (!response.ok) throw new Error(t('expenses.request_failed_status', {status: response.status}));
      const fresh = new window.DOMParser().parseFromString(await response.text(), 'text/html');
      const updatedSummary = fresh.querySelector('#expense-summary');
      const updatedRecords = fresh.querySelector('#expense-records');
      if (!updatedSummary || !updatedRecords) throw new Error(t('expenses.refresh_failed'));
      // Retain unrelated row controls and unsaved overlap notes. Only changed rows
      // receive new server-rendered statuses, actions and confirmation fingerprints.
      for (const row of records.querySelectorAll('[data-expense-id]')) {
        const next = updatedRecords.querySelector(`[data-expense-id="${Number(row.dataset.expenseId)}"]`);
        if (!next) row.remove();
        else if (next.dataset.expenseToken !== row.dataset.expenseToken) {
          const replacement = next.cloneNode(true);
          row.replaceWith(replacement);
          if (!focusTarget?.isConnected) focusTarget = replacement.querySelector('button, input');
        }
      }
      const freshRows = [...updatedRecords.querySelectorAll('[data-expense-id]')];
      if (!freshRows.length || !records.querySelector('tbody')) records.replaceChildren(...updatedRecords.childNodes);
      else for (const row of freshRows) {
        const retained = records.querySelector(`[data-expense-id="${Number(row.dataset.expenseId)}"]`);
        records.querySelector('tbody').append(retained || row);
      }
      summary.replaceChildren(...updatedSummary.childNodes);
      enhanceExpenseTables(summary);
      records.querySelectorAll('button').forEach(node => node.classList.add('fv-button'));
      records.querySelectorAll('input').forEach(node => node.classList.add('fv-input'));
      records.querySelectorAll('button[type="submit"]').forEach(node => node.classList.add('fv-button--primary'));
      summary.hidden = false;
      feedback.textContent = t(uncertain ? 'expenses.delete_reconciled' : 'expenses.deleted');
      uncertain = false;
      feedback.setAttribute('role', 'status');
      feedback.hidden = false;
      setDialogBusy(dialog, false);
      dismiss();
    } catch {
      const failure = t(uncertain ? 'expenses.delete_uncertain' : 'expenses.refresh_failed');
      message.textContent = failure;
      message.lang = locale;
      message.setAttribute('role', 'alert');
      message.hidden = false;
      setDialogBusy(dialog, false);
      retry.hidden = false;
      if (dialog.open) retry.focus({preventScroll: true});
      feedback.textContent = failure;
      feedback.setAttribute('role', 'alert');
      const retryRead = document.createElement('button');
      retryRead.type = 'button';
      retryRead.className = 'fv-button';
      retryRead.textContent = t('expenses.retry_refresh');
      retryRead.addEventListener('click', () => {if (!dialogs.get(dialog).busy) refresh();});
      feedback.append(' ', retryRead);
    }
  }
  retry.addEventListener('click', () => {if (!dialogs.get(dialog).busy) refresh();});
  confirm.addEventListener('click', async () => {
    if (!selected || dialogs.get(dialog).busy) return;
    setDialogBusy(dialog, true);
    message.hidden = false;
    message.textContent = t('expenses.deleting');
    message.classList.remove('error');
    message.lang = locale;
    message.setAttribute('role', 'status');
    let response;
    try {
      response = await fetch(`/api/expenses/${selected.id}`, {
        method: 'DELETE', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({expected_token: selected.expected_token}),
      });
      if (!response.ok) await responseJson(response);
    } catch (error) {
      if (!response || response.status >= 500) {
        // A lost response or server failure does not establish whether the write
        // committed. Reconcile using reads and require a fresh confirmation.
        uncertain = true;
        selected = null;
        confirm.hidden = true;
        summary.hidden = true;
        await refresh();
        return;
      }
      message.textContent = error.message;
      message.lang = error.language || locale;
      message.setAttribute('role', 'alert');
      message.classList.add('error');
      setDialogBusy(dialog, false);
      return;
    }
    records.querySelector(`[data-expense-id="${Number(selected.id)}"]`)?.remove();
    selected = null;
    confirm.hidden = true;
    summary.hidden = true;
    feedback.textContent = t('expenses.deleted');
    feedback.hidden = false;
    await refresh();
  });
}

initializeExpenseDeletion();

// Read-only server-rendered provenance stays out of the compact table.
document.addEventListener('click', event => {
  const action = event.target.closest('[data-expense-view]');
  if (!action) return;
  const template = document.getElementById(`expense-details-${Number(action.dataset.expenseView)}`);
  if (!template) return;
  document.querySelector('#expense-details-content').replaceChildren(template.content.cloneNode(true));
  openDialog(document.querySelector('#expense-details-dialog'));
});
