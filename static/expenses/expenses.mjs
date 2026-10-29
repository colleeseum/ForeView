// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {formatMoneyDollars, formatDisplayDate} from '../shared/locale-format.mjs';

import {t, locale} from '../shared/i18n.mjs';
import {createDialog} from '../shared/dialog.mjs';

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
document.querySelectorAll('.fv-expenses .table-card').forEach(region => {
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
document.querySelectorAll('[data-expense-edit]').forEach(button => button.addEventListener('click', () => {
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
}));
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
  let helpGeneration = 0;
  dialog.addEventListener('click', async event => {
    const button = event.target.closest('[data-help-article]');
    if (!button) return;
    event.stopPropagation();
    const generation = ++helpGeneration;
    let panel = dialog.querySelector('[data-import-help]');
    if (!panel) {
      panel = document.createElement('section');
      panel.dataset.importHelp = '';
      panel.className = 'fv-feedback';
      panel.tabIndex = -1;
      button.after(panel);
    }
    panel.textContent = t('help.loading');
    panel.focus();
    try {
      const response = await fetch('/api/help');
      if (!response.ok) throw new Error(t('help.unavailable'));
      const data = await response.json();
      if (generation !== helpGeneration) return;
      const article = data.articles.find(item => item.key === button.dataset.helpArticle);
      if (!article) throw new Error(t('help.unavailable'));
      panel.replaceChildren(...['title', 'summary', 'body'].filter(field => article[field]).map(field => {
        const node = document.createElement(field === 'title' ? 'strong' : 'p');
        node.textContent = article[field];
        node.lang = article.field_languages?.[field] || article.language || data.language || locale;
        return node;
      }));
    } catch (error) {if (generation === helpGeneration) panel.textContent = error.message;}
  });

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
      replacingFailedFile = false;
      previewStep.tabIndex = -1;
      previewStep.focus();
    } catch (error) {
      replacingFailedFile = true;
      if (fileStep) fileStep.hidden = false;
      if (previewStep) previewStep.hidden = true;
      if (confirmButton) confirmButton.hidden = true;
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
