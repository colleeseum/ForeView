// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {t, locale} from './i18n.mjs';

const expenseDialog = document.querySelector('#expense-dialog-backdrop');
const categoryDialog = document.querySelector('#category-dialog-backdrop');
const categoryEditor = document.querySelector('#category-editor-backdrop');
const categoryForm = document.querySelector('#category-editor-form');
const categoryTitle = document.querySelector('#category-editor-title');
const categoryStatus = document.querySelector('#category-status-field');
const categorySave = document.querySelector('#category-editor-save');
const expenseYearSelect = document.querySelector('#expense-year-select');

expenseYearSelect?.addEventListener('change', () => expenseYearSelect.form?.requestSubmit());

export function importCompletionUrl(savedCount, savedYears, selectedYear, origin) {
  const nextUrl = new URL('/expenses', origin);
  nextUrl.searchParams.set('year', String(selectedYear));
  nextUrl.searchParams.set('imported', String(savedCount));
  nextUrl.searchParams.set('imported_years', [...savedYears].sort((left, right) => left - right).join(','));
  return nextUrl;
}

function openDialog(dialog) {
  dialog.hidden = false;
  dialog.querySelector('.dialog-close').focus();
}

function closeDialog(dialog) {
  dialog.hidden = true;
}

function openCategoryEditor(button = null) {
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

document.querySelector('#expense-add').addEventListener('click', () => openDialog(expenseDialog));
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

document.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape') return;
  if (!categoryEditor.hidden) {
    returnToCategories();
    return;
  }
  closeDialog(expenseDialog);
  closeDialog(categoryDialog);
});

function initializeExpenseImport() {
  const dialog = document.querySelector('#expense-import-dialog-backdrop');
  const openButton = document.querySelector('#expense-import');
  if (!dialog || !openButton) return;

  const form = document.querySelector('#expense-import-form');
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
    clearError();
    if (fileStep) fileStep.hidden = false;
    if (previewStep) previewStep.hidden = true;
    if (confirmButton) confirmButton.hidden = true;
    updateQueueStatus();
    setBusy(false);
  }

  function dismiss() {
    closeDialog(dialog);
    reset();
  }

  async function responseJson(response) {
    let result = {};
    try {
      result = await response.json();
    } catch {
      if (!response.ok) {
        const error = new Error(t('expenses.request_failed_status', {status: response.status}));
        error.language = locale;
        throw error;
      }
    }
    if (!response.ok) {
      const error = new Error(result.error || t('expenses.request_failed_status', {status: response.status}));
      error.language = result.error ? 'en-CA' : locale;
      throw error;
    }
    return result;
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
    if (previewButton) previewButton.disabled = !currentFile();
  });

  async function previewCurrentFile() {
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
      providerKey.value = preview.provider_key;
      amount.textContent = preview.amount;
      periodStart.textContent = preview.period_start;
      periodEnd.textContent = preview.period_end;
      name.value = preview.suggested_identity;
      association.value = 'household';
      fileStep.hidden = true;
      previewStep.hidden = false;
      confirmButton.hidden = false;
      replacingFailedFile = false;
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
    const file = currentFile();
    if (!file || !name || !category || !providerKey) return;
    if (!name.reportValidity() || !category.reportValidity()) return;
    clearError();
    setBusy(true, progressText?.dataset.savingText || t('expenses.saving'));
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
      await responseJson(response);
      savedCount += 1;
      const startYear = Number(periodStart.textContent.slice(0, 4));
      const endYear = Number(periodEnd.textContent.slice(0, 4));
      for (let year = startYear; year <= endYear; year += 1) savedYears.add(year);
      if (currentFileIndex + 1 < pendingFiles.length) {
        currentFileIndex += 1;
        previewStep.hidden = true;
        confirmButton.hidden = true;
        await previewCurrentFile();
        return;
      }
      const nextUrl = importCompletionUrl(
        savedCount,
        savedYears,
        periodEnd.textContent.slice(0, 4),
        window.location.origin,
      );
      window.location.assign(nextUrl);
    } catch (error) {
      showError(error);
      setBusy(false);
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !dialog.hidden) dismiss();
  });
}

initializeExpenseImport();
