// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

const expenseDialog = document.querySelector('#expense-dialog-backdrop');
const categoryDialog = document.querySelector('#category-dialog-backdrop');
const categoryEditor = document.querySelector('#category-editor-backdrop');
const categoryForm = document.querySelector('#category-editor-form');
const categoryTitle = document.querySelector('#category-editor-title');
const categoryStatus = document.querySelector('#category-status-field');
const categorySave = document.querySelector('#category-editor-save');

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
    categoryTitle.textContent = 'Edit category';
    categorySave.textContent = 'Save category';
    categoryStatus.hidden = false;
  } else {
    categoryForm.action = categoryForm.dataset.createAction;
    categoryTitle.textContent = 'Add category';
    categorySave.textContent = 'Create category';
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
