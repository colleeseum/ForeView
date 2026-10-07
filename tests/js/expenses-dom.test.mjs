// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import test from 'node:test';
import {JSDOM} from 'jsdom';

test('expense actions use closable dialogs without backdrop-click dismissal', async () => {
  const dom = new JSDOM(`<!doctype html><body>
    <form id="expense-year-form"><select id="expense-year-select" name="year"><option value="2025">2025</option><option value="2026">2026</option></select></form>
    <button id="expense-add"></button><button id="expense-categories"></button>
    <div id="expense-dialog-backdrop" hidden><section><button id="expense-dialog-close" class="dialog-close"></button><button id="expense-dialog-cancel"></button><button id="expense-open-categories"></button></section></div>
    <div id="category-dialog-backdrop" hidden><section><button id="category-dialog-close" class="dialog-close"></button><button id="category-add"></button><button data-category-edit data-action="/expenses/categories/7" data-name="Utilities" data-classification="required" data-active="true"></button></section></div>
    <div id="category-editor-backdrop" hidden><section><button id="category-editor-close" class="dialog-close"></button><h2 id="category-editor-title" data-add-text="Ajouter une catégorie" data-edit-text="Modifier la catégorie"></h2><form id="category-editor-form" action="/expenses/categories" data-create-action="/expenses/categories"><input name="name"><select name="classification"><option value="required">Required</option><option value="discretionary">Discretionary</option></select><label id="category-status-field" hidden><select name="active"><option value="true">Active</option><option value="false">Archived</option></select></label><button id="category-editor-cancel" type="button"></button><button id="category-editor-save" type="submit" data-create-text="Créer une catégorie" data-save-text="Enregistrer la catégorie"></button></form></section></div>
  </body>`, {url: 'http://localhost/expenses'});
  Object.assign(globalThis, {window: dom.window, document: dom.window.document});

  let yearSubmissions = 0;
  document.querySelector('#expense-year-form').requestSubmit = () => { yearSubmissions += 1; };

  await import('../../static/expenses.mjs');
  const expenseDialog = document.querySelector('#expense-dialog-backdrop');
  const categoryDialog = document.querySelector('#category-dialog-backdrop');
  const categoryEditor = document.querySelector('#category-editor-backdrop');

  const yearSelect = document.querySelector('#expense-year-select');
  yearSelect.value = '2026';
  yearSelect.dispatchEvent(new dom.window.Event('change', {bubbles: true}));
  assert.equal(yearSubmissions, 1);

  document.querySelector('#expense-add').click();
  assert.equal(expenseDialog.hidden, false);
  expenseDialog.click();
  assert.equal(expenseDialog.hidden, false);
  document.querySelector('#expense-dialog-cancel').click();
  assert.equal(expenseDialog.hidden, true);

  document.querySelector('#expense-add').click();
  document.querySelector('#expense-open-categories').click();
  assert.equal(expenseDialog.hidden, true);
  assert.equal(categoryDialog.hidden, false);
  document.querySelector('#category-dialog-close').click();
  assert.equal(categoryDialog.hidden, true);

  document.querySelector('#expense-categories').click();
  document.querySelector('#category-add').click();
  assert.equal(categoryDialog.hidden, true);
  assert.equal(categoryEditor.hidden, false);
  assert.equal(document.querySelector('#category-editor-title').textContent, 'Ajouter une catégorie');
  assert.equal(document.querySelector('#category-editor-save').textContent, 'Créer une catégorie');
  assert.equal(document.querySelector('#category-status-field').hidden, true);
  document.querySelector('#category-editor-cancel').click();
  assert.equal(categoryDialog.hidden, false);
  assert.equal(categoryEditor.hidden, true);

  document.querySelector('[data-category-edit]').click();
  assert.equal(document.querySelector('#category-editor-form').action.endsWith('/expenses/categories/7'), true);
  assert.equal(document.querySelector('#category-editor-form').elements.name.value, 'Utilities');
  assert.equal(document.querySelector('#category-editor-title').textContent, 'Modifier la catégorie');
  assert.equal(document.querySelector('#category-editor-save').textContent, 'Enregistrer la catégorie');
  assert.equal(document.querySelector('#category-status-field').hidden, false);
  document.querySelector('#category-editor-close').click();
  assert.equal(categoryDialog.hidden, false);

  document.querySelector('#expense-categories').click();
  assert.equal(categoryDialog.hidden, false);
  document.dispatchEvent(new dom.window.KeyboardEvent('keydown', {key: 'Enter'}));
  assert.equal(categoryDialog.hidden, false);
  document.dispatchEvent(new dom.window.KeyboardEvent('keydown', {key: 'Escape'}));
  assert.equal(categoryDialog.hidden, true);

  document.querySelector('#expense-categories').click();
  document.querySelector('#category-add').click();
  document.dispatchEvent(new dom.window.KeyboardEvent('keydown', {key: 'Escape'}));
  assert.equal(categoryEditor.hidden, true);
  assert.equal(categoryDialog.hidden, false);
  document.querySelector('#category-dialog-close').click();

  document.querySelector('#expense-add').click();
  document.querySelector('#expense-dialog-close').click();
  assert.equal(expenseDialog.hidden, true);
  dom.window.close();
});
