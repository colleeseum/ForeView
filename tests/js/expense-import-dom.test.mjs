// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import test from 'node:test';

import {JSDOM} from 'jsdom';
import {configureTestLocalization} from './localization-fixture.mjs';

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

test('expense import reviews parser evidence and displays confirmation errors', async () => {
  configureTestLocalization();
  const dom = new JSDOM(`<!doctype html><body>
    <button id="expense-add"></button><button id="expense-categories"></button>
    <div id="expense-dialog-backdrop" hidden><section><button id="expense-dialog-close" class="dialog-close"></button><button id="expense-dialog-cancel"></button><button id="expense-open-categories"></button></section></div>
    <div id="category-dialog-backdrop" hidden><section><button id="category-dialog-close" class="dialog-close"></button><button id="category-add"></button></section></div>
    <div id="category-editor-backdrop" hidden><section><button id="category-editor-close" class="dialog-close"></button><h2 id="category-editor-title"></h2><form id="category-editor-form" data-create-action="/expenses/categories"><input name="name"><select name="classification"><option value="required">Required</option></select><label id="category-status-field"><select name="active"><option value="true">Active</option></select></label><button id="category-editor-cancel"></button><button id="category-editor-save"></button></form></section></div>
    <button id="expense-import"></button>
    <div id="expense-import-dialog-backdrop" hidden><section><button id="expense-import-close" class="dialog-close"></button>
      <form id="expense-import-form">
        <div id="import-step-file"><input id="expense-import-file" type="file" multiple><button id="import-preview-btn" type="button" disabled></button></div>
        <p id="expense-import-queue-status" hidden></p>
        <div id="expense-import-progress" hidden><span></span></div><p id="expense-import-message" hidden></p>
        <div id="import-step-preview" hidden><span id="import-provider"></span><span id="import-amount"></span><span id="import-period-start"></span><span id="import-period-end"></span><input id="import-name" required><select id="import-category"><option value="8">Electricity</option></select><select id="import-association"><option value="household">Household</option><option value="person:3">Person</option></select></div>
        <input id="import-provider-key">
      </form>
      <button id="import-cancel"></button><button id="import-confirm" type="button" hidden></button><button id="import-open-categories" type="button"></button>
    </section></div>
  </body>`, {url: 'http://localhost/expenses'});
  Object.assign(globalThis, {
    window: dom.window,
    document: dom.window.document,
    FormData: dom.window.FormData,
  });
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({url: String(url), options});
    if (String(url).endsWith('/preview')) {
      const filename = options.body.get('file').name;
      const second = filename.includes('hydro-february');
      const third = filename.includes('hydro-march');
      if (filename === 'hydro-february.pdf') {
        return {
          ok: false,
          status: 400,
          json: async () => ({error: 'The second PDF could not be analysed.'}),
        };
      }
      return {
        ok: true,
        status: 200,
        json: async () => ({preview: {
            provider_key: 'hydro-quebec',
            provider_display_name: 'Hydro-Québec electricity bill',
            amount: third ? '52.00' : second ? '45.00' : '31.00',
            period_start: third ? '2026-03-01' : second ? '2026-02-01' : '2026-01-01',
            period_end: third ? '2026-03-31' : second ? '2026-02-28' : '2026-01-31',
            suggested_identity: 'Hydro',
        }}),
      };
    }
    if (options.body.get('file').name !== 'hydro-march.pdf') {
      return {ok: true, status: 201, json: async () => ({id: 1})};
    }
    return {
      ok: false,
      status: 400,
      json: async () => ({error: 'Category is no longer active.'}),
    };
  };

  const module = await import(`../../static/expenses.mjs?import=${Date.now()}`);
  const completionUrl = module.importCompletionUrl(12, new Set([2026, 2024, 2025]), 2026, 'http://localhost');
  assert.equal(completionUrl.pathname, '/expenses');
  assert.equal(completionUrl.searchParams.get('year'), '2026');
  assert.equal(completionUrl.searchParams.get('imported'), '12');
  assert.equal(completionUrl.searchParams.get('imported_years'), '2024,2025,2026');
  document.querySelector('#expense-import').click();
  const fileInput = document.querySelector('#expense-import-file');
  Object.defineProperty(fileInput, 'files', {
    configurable: true,
    value: [
      new dom.window.File(['pdf'], 'hydro-january.pdf', {type: 'application/pdf'}),
      new dom.window.File(['pdf'], 'hydro-february.pdf', {type: 'application/pdf'}),
      new dom.window.File(['pdf'], 'hydro-march.pdf', {type: 'application/pdf'}),
    ],
  });
  fileInput.dispatchEvent(new dom.window.Event('change', {bubbles: true}));
  const previewButton = document.querySelector('#import-preview-btn');
  assert.equal(previewButton.disabled, false);
  assert.match(document.querySelector('#expense-import-queue-status').textContent, /1 of 3/);
  previewButton.click();
  assert.equal(document.querySelector('#expense-import-progress').hidden, false);
  await tick();

  assert.equal(document.querySelector('#expense-import-progress').hidden, true);
  assert.equal(document.querySelector('#import-step-preview').hidden, false);
  assert.equal(document.querySelector('#import-amount').textContent, '31.00');
  assert.equal(document.querySelector('#import-amount').tagName, 'SPAN');
  assert.equal(document.querySelector('#import-period-start').textContent, '2026-01-01');
  assert.equal(document.querySelector('#import-period-start').tagName, 'SPAN');
  assert.equal(document.querySelector('#import-confirm').hidden, false);

  document.querySelector('#import-association').value = 'person:3';
  document.querySelector('#import-confirm').click();
  await tick(); await tick();

  const confirmation = calls.find(({url}) => url.endsWith('/confirm'));
  const fields = Object.fromEntries(confirmation.options.body.entries());
  assert.equal(fields.provider_key, 'hydro-quebec');
  assert.equal(fields.category_id, '8');
  assert.equal(fields.association, 'person:3');
  assert.equal('period_start' in fields, false);
  assert.equal('period_end' in fields, false);

  assert.match(document.querySelector('#expense-import-queue-status').textContent, /2 of 3/);
  assert.match(document.querySelector('#expense-import-queue-status').textContent, /1 saved/);
  assert.match(document.querySelector('#expense-import-queue-status').textContent, /hydro-february/);
  assert.equal(document.querySelector('#import-step-file').hidden, false);
  assert.equal(document.querySelector('#import-step-preview').hidden, true);
  assert.equal(document.querySelector('#import-confirm').hidden, true);
  assert.match(document.querySelector('#expense-import-message').textContent, /could not be analysed/);
  assert.equal(document.querySelector('#expense-import-message').lang, 'en-CA');

  Object.defineProperty(fileInput, 'files', {
    configurable: true,
    value: [
      new dom.window.File(['pdf'], 'hydro-february-replacement.pdf', {type: 'application/pdf'}),
    ],
  });
  fileInput.dispatchEvent(new dom.window.Event('change', {bubbles: true}));
  assert.match(document.querySelector('#expense-import-queue-status').textContent, /1 saved/);
  assert.match(document.querySelector('#expense-import-queue-status').textContent, /2 of 3/);
  assert.match(document.querySelector('#expense-import-queue-status').textContent, /replacement/);

  previewButton.click();
  await tick();
  assert.equal(document.querySelector('#import-amount').textContent, '45.00');
  assert.equal(document.querySelector('#import-period-start').textContent, '2026-02-01');
  assert.equal(document.querySelector('#import-step-file').hidden, true);
  assert.equal(document.querySelector('#import-step-preview').hidden, false);

  document.querySelector('#import-confirm').click();
  await tick();
  await tick();
  assert.match(document.querySelector('#expense-import-queue-status').textContent, /3 of 3/);
  assert.match(document.querySelector('#expense-import-queue-status').textContent, /2 saved/);
  assert.match(document.querySelector('#expense-import-queue-status').textContent, /hydro-march/);
  assert.equal(document.querySelector('#import-amount').textContent, '52.00');
  assert.equal(document.querySelector('#import-period-start').textContent, '2026-03-01');

  document.querySelector('#import-confirm').click();
  await tick();
  assert.equal(document.querySelector('#expense-import-message').hidden, false);
  assert.match(document.querySelector('#expense-import-message').textContent, /no longer active/);
  assert.equal(document.querySelector('#expense-import-message').lang, 'en-CA');

  document.querySelector('#import-open-categories').click();
  assert.equal(document.querySelector('#expense-import-dialog-backdrop').hidden, true);
  assert.equal(document.querySelector('#category-editor-backdrop').hidden, false);
  assert.equal(document.querySelector('#category-editor-title').textContent, 'Add category');
  dom.window.close();
});
