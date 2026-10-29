// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import test from 'node:test';
import {JSDOM} from 'jsdom';
import {configureTestLocalization} from './localization-fixture.mjs';

const tick = () => new Promise(resolve => setTimeout(resolve, 0));

test('expense deletion updates in place and retries only reads after a committed mutation', async () => {
  configureTestLocalization('fr-CA');
  const dom = new JSDOM(`<!doctype html><body><main class="fv-expenses">
    <button id="expense-add"></button><button id="expense-categories"></button>
    <dialog id="expense-dialog-backdrop"><button id="expense-dialog-close"></button><button id="expense-dialog-cancel"></button><button id="expense-open-categories"></button></dialog>
    <dialog id="category-dialog-backdrop"><button id="category-dialog-close"></button><button id="category-add"></button></dialog>
    <dialog id="category-editor-backdrop"><button id="category-editor-close"></button><button id="category-editor-cancel"></button></dialog>
    <select id="expense-year-select"><option value="2026">2026</option></select>
    <div id="expense-summary"><strong>Old total</strong></div>
    <details class="expense-record-details" open><summary>Records</summary><p id="expense-record-feedback" hidden></p><div id="expense-records"><table><tbody>
      <tr data-expense-id="7" data-expense-token="old"><td><button data-expense-delete></button></td></tr>
      <tr data-expense-id="8" data-expense-token="old"><td><button data-expense-delete></button></td></tr>
      <tr data-expense-id="9" data-expense-token="stable"><td><input name="note" value="Unsaved unrelated draft"></td></tr>
    </tbody></table></div></details>
    <dialog id="expense-delete-dialog" hidden><p id="expense-delete-details"></p><p id="expense-delete-message" hidden></p><button id="expense-delete-close"></button><button id="expense-delete-cancel"></button><button id="expense-delete-refresh" hidden></button><button id="expense-delete-confirm"></button></dialog>
  </main></body>`, {url: 'http://localhost/expenses'});
  const document = dom.window.document;
  for (const dialog of document.querySelectorAll('dialog')) {
    dialog.showModal = () => {dialog.open = true;};
    dialog.close = () => {dialog.open = false; dialog.dispatchEvent(new dom.window.Event('close'));};
  }
  const navigation = [];
  const positions = [];
  Object.assign(globalThis, {document, window: {DOMParser: dom.window.DOMParser, scrollX: 40, scrollY: 800, scrollTo: position => positions.push(position), location: {origin: 'http://localhost', assign: url => {
    navigation.push(String(url));
    throw new Error('Synthetic navigation unavailable');
  }}}});
  const record = {id: 7, name: '<script>evidence</script>', source_name: 'synthetic.pdf', amount: '31.00', period_start: '2026-01-01', period_end: '2026-01-31', expected_token: 'synthetic-guard'};
  const trigger = document.querySelector('[data-expense-delete]');
  trigger.dataset.expenseDelete = JSON.stringify(record);
  const requests = [];
  let respond;
  let reject;
  globalThis.fetch = (url, options) => {
    requests.push({url, options});
    return new Promise((resolve, fail) => {respond = resolve; reject = fail;});
  };
  try {
    await import(`../../static/expenses/expenses.mjs?deletion=${Date.now()}`);
    trigger.click();
    const dialog = document.querySelector('#expense-delete-dialog');
    const confirm = document.querySelector('#expense-delete-confirm');
    const cancel = document.querySelector('#expense-delete-cancel');
    const feedback = document.querySelector('#expense-delete-message');
    assert.equal(dialog.open, true);
    assert(document.querySelector('#expense-delete-details').textContent.includes(record.name));
    assert.equal(dialog.querySelector('script'), null);
    cancel.click();
    assert.equal(dialog.open, false);
    assert.equal(requests.length, 0);
    trigger.click();
    confirm.click();
    assert.equal(cancel.disabled, true);
    confirm.dispatchEvent(new dom.window.Event('click'));
    trigger.dispatchEvent(new dom.window.Event('click'));
    assert.equal(requests.length, 1);
    assert.equal(requests[0].options.method, 'DELETE');
    assert.deepEqual(JSON.parse(requests[0].options.body), {expected_token: record.expected_token});
    cancel.dispatchEvent(new dom.window.Event('click'));
    assert.equal(dialog.open, true);
    respond({ok: false, status: 409, json: async () => ({error: 'Synthetic stale evidence', error_language: 'en-CA'})});
    await tick();
    assert.equal(feedback.getAttribute('role'), 'alert');
    assert.equal(feedback.lang, 'en-CA');
    assert.equal(feedback.textContent, 'Synthetic stale evidence');
    assert.equal(confirm.disabled, false);
    confirm.click();
    respond({ok: true, status: 204, json: () => {throw new Error('204 must not be parsed');}});
    await tick();
    assert.equal(requests.length, 3);
    assert.equal(requests[2].options.cache, 'no-store');
    assert.equal(document.querySelector('[data-expense-id="7"]'), null);
    assert.equal(document.querySelector('#expense-summary').hidden, true);
    respond({ok: false, status: 503});
    await tick();
    assert.equal(feedback.getAttribute('role'), 'alert');
    const refresh = document.querySelector('#expense-delete-refresh');
    assert.equal(refresh.hidden, false);
    assert.equal(document.activeElement, refresh);
    confirm.dispatchEvent(new dom.window.Event('click'));
    assert.equal(requests.length, 3);
    refresh.click();
    const fresh = `<div id="expense-summary"><strong>31,00 $</strong></div><div id="expense-records"><table><tbody>
      <tr data-expense-id="8" data-expense-token="new"><td><button data-expense-delete='${JSON.stringify({...record, id: 8, expected_token: 'new'})}'>Delete</button></td></tr>
      <tr data-expense-id="9" data-expense-token="stable"><td><input name="note" value="Server note"></td></tr>
    </tbody></table></div>`;
    respond({ok: true, text: async () => fresh});
    await tick();
    assert.equal(requests.length, 4);
    assert.equal(requests.filter(request => request.options.method === 'DELETE').length, 2);
    assert.equal(navigation.length, 0);
    assert.equal(dialog.open, false);
    assert.equal(document.querySelector('#expense-summary').hidden, false);
    assert.equal(document.querySelector('#expense-summary').textContent, '31,00 $');
    assert.equal(document.querySelector('[name="note"]').value, 'Unsaved unrelated draft');
    assert.deepEqual([...document.querySelectorAll('[data-expense-id]')].map(row => row.dataset.expenseId), ['8', '9']);
    assert.equal(document.querySelector('.expense-record-details').open, true);
    assert.equal(document.activeElement, document.querySelector('[data-expense-id="8"] button'));
    assert.deepEqual(positions.at(-1), {left: 40, top: 800});
    document.querySelector('[data-expense-id="8"] button').click();
    confirm.click();
    assert.deepEqual(JSON.parse(requests.at(-1).options.body), {expected_token: 'new'});
    respond({ok: false, status: 409, json: async () => ({error: 'Synthetic changed record'})});
    await tick();
    // The server may commit before the connection fails. Never resend that DELETE.
    confirm.click();
    const mutationCount = requests.filter(request => request.options.method === 'DELETE').length;
    reject(new TypeError('Synthetic connection dropped after commit'));
    await tick();
    assert.equal(requests.at(-1).options.method, undefined);
    respond({ok: false, status: 503});
    await tick();
    assert.equal(document.activeElement, refresh);
    assert.equal(confirm.hidden, true);
    confirm.dispatchEvent(new dom.window.Event('click'));
    assert.equal(requests.filter(request => request.options.method === 'DELETE').length, mutationCount);
    refresh.click();
    respond({ok: true, text: async () => fresh.replace(/<tr data-expense-id="8"[\s\S]*?<\/tr>/, '')});
    await tick();
    assert.equal(document.querySelector('[data-expense-id="8"]'), null);
    assert.equal(dialog.open, false);
    assert.equal(requests.filter(request => request.options.method === 'DELETE').length, mutationCount);
    // A failed server response can also precede rollback: keep surviving evidence
    // and require the user to reopen a new confirmation after reconciliation.
    const table = document.querySelector('#expense-records tbody');
    table.insertAdjacentHTML('beforeend', `<tr data-expense-id="10" data-expense-token="ten"><td><button data-expense-delete='${JSON.stringify({...record, id: 10, expected_token: 'ten'})}'>Delete</button></td></tr>`);
    document.querySelector('[data-expense-id="10"] button').click();
    confirm.click();
    respond({ok: false, status: 500, json: async () => ({error: 'Synthetic server failure'})});
    await tick();
    const current = `<div id="expense-summary">Current total</div><div id="expense-records">${document.querySelector('#expense-records').innerHTML}</div>`;
    respond({ok: true, text: async () => current});
    await tick();
    assert.equal(dialog.open, false);
    assert(document.querySelector('[data-expense-id="10"]'));
    assert(document.querySelector('#expense-record-feedback').textContent.includes('actualisée'));
    assert.equal(document.querySelector('#expense-summary').hidden, false);
  } finally {
    dom.window.close();
    for (const key of ['window', 'document', 'fetch']) delete globalThis[key];
  }
});
