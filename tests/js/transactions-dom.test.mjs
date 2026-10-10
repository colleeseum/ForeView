// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import test from 'node:test';
import {JSDOM} from 'jsdom';
import {configureTestLocalization} from './localization-fixture.mjs';
import {transactionsTableHtml} from '../../static/transactions-render.mjs';

test('transaction table keeps canonical openings and malformed evidence in semantic order', () => {
  configureTestLocalization();
  const rows = [
    {id: 1, transaction_date: '2026-01-20', amount: 50, description: 'Later'},
    {id: 2, transaction_date: 'not-a-date', amount: 5, description: 'Malformed'},
    {id: 3, transaction_date: '2026-02-30', amount: 5, description: 'Invalid calendar'},
    {id: 4, transaction_date: '2026-01-15', amount: 5, description: 'Same day'},
    {id: 5, transaction_date: '2026-01-10', amount: 5, description: 'Earlier'},
  ];
  const openings = [
    {id: 'opening-1', transaction_date: '2026-01-15', is_opening_balance: true, description: 'Opening'},
  ];
  const dom = new JSDOM(transactionsTableHtml(rows, openings, true));
  assert.deepEqual(
    [...dom.window.document.querySelectorAll('tbody tr')].map((row) => row.cells[2].textContent),
    ['Later', 'Same day', 'Opening', 'Earlier', 'Malformed', 'Invalid calendar'],
  );
  dom.window.close();
});

function installDom() {
  configureTestLocalization();
  const dom = new JSDOM(`<!doctype html><body>
    <button class="view-tab" data-type="non_registered"></button><button class="view-tab" data-type="tfsa"></button><button class="view-tab" data-type="rrsp"></button>
    <select id="transaction-account-filter"><option value="">All</option></select>
    <button id="open-reconcile-button"></button><button id="open-import-button"></button>
    <span id="breadcrumb-category"></span><span id="breadcrumb-account"></span><p id="reconciliation-status" hidden></p>
    <div id="transactions-table-content"></div><div id="import-history-content"></div>
    <div id="import-dialog" hidden><button id="close-import-dialog"></button><h2 id="import-dialog-title"></h2><p id="import-dialog-description" data-default-text="Help"></p>
      <form id="transaction-import-form"><select id="transaction-account" name="account_id"></select><input name="files" type="file"><button id="import-submit-button" type="submit"></button></form><p id="import-result"></p>
    </div>
    <div id="reconcile-dialog" hidden><button id="close-reconcile-dialog"></button>
      <form id="reconcile-form"><input id="reconcile-account-label"><input id="reconcile-date" name="date"><input id="reconcile-amount" name="amount"><button id="reconcile-submit-button" type="submit"></button></form><p id="reconcile-result"></p>
    </div><div id="toast" hidden></div>
  </body>`, {url: 'http://localhost/transactions?type=non_registered'});
  Object.assign(globalThis, {
    window: dom.window,
    document: dom.window.document,
    FormData: dom.window.FormData,
    File: dom.window.File,
    Option: dom.window.Option,
  });
  return dom;
}

const wait = () => new Promise((resolve) => setTimeout(resolve, 0));
const jsonResponse = (data, ok = true, status = 200) => ({ok, status, text: async () => JSON.stringify(data), json: async () => data});

test('transactions module loads filters and reconciles the selected account', async () => {
  const dom = installDom();
  const attack = '<svg onload=alert(1)>';
  const calls = [];
  let importMode = 'success';
  let reconcileError = false;
  globalThis.fetch = async (url, options = {}) => {
    calls.push([String(url), options]);
    if (url === '/api/model/accounts') return jsonResponse({accounts: [{id: 1, account_type: 'non_registered', asset_kind: 'account', account_number: 'A1', institution: 'Bank', name: 'Daily'}]});
    if (String(url).startsWith('/api/model/transactions?')) return jsonResponse({transactions: [{transaction_date: '2026-09-01', institution: 'Bank', account_number: 'A1', description: attack, amount: 25, category: attack, balance_after: 125, combined_balance_after: 125}], opening_balances: []});
    if (String(url).startsWith('/api/model/import-history?')) return jsonResponse({imports: [{imported_at: '2026-09-02', filename: attack, account_number: 'A1', row_count: 1}]});
    if (url === '/api/model/accounts/1/reconciliation') return jsonResponse({reconciled_through: '2026-09-01', checkpoints: []});
    if (url === '/api/model/accounts/1/reconcile') {
      return reconcileError
        ? jsonResponse({error: 'Balance is invalid'}, false, 400)
        : jsonResponse({difference: 0, reconciled_through: '2026-09-01'});
    }
    if (url === '/api/model/transactions/import') {
      if (importMode === 'conflict') return jsonResponse({confirm_reconciled: true, error: 'Reconciled period'}, false, 409);
      if (importMode === 'error') return jsonResponse({error: 'Unknown document', help_url: '/help'}, false, 400);
      return jsonResponse({imported: 1, files: 1, results: []});
    }
    throw new Error(`Unexpected fetch: ${url}`);
  };

  await import('../../static/transactions.mjs');
  await wait();
  await wait();

  const table = document.querySelector('#transactions-table-content');
  assert.match(table.textContent, /2026-09-01/);
  assert.equal(table.innerHTML.includes(attack), false);
  assert.equal(document.querySelector('#import-history-content').innerHTML.includes(attack), false);

  const filter = document.querySelector('#transaction-account-filter');
  filter.value = '1';
  filter.dispatchEvent(new dom.window.Event('change'));
  await wait();
  assert.match(document.querySelector('#reconciliation-status').textContent, /Reconciled through/);

  document.querySelector('#open-reconcile-button').click();
  document.querySelector('#reconcile-date').value = '2026-09-01';
  document.querySelector('#reconcile-amount').value = '125';
  document.querySelector('#reconcile-form').dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
  await wait();
  await wait();
  assert.equal(document.querySelector('#reconcile-dialog').hidden, true);
  assert.equal(calls.some(([url, options]) => url === '/api/model/accounts/1/reconcile' && options.method === 'POST'), true);

  document.querySelector('#open-reconcile-button').click();
  reconcileError = true;
  document.querySelector('#reconcile-form').dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
  await wait();
  assert.match(document.querySelector('#reconcile-result').textContent, /Balance is invalid/);
  assert.equal(document.querySelector('#reconcile-result').lang, 'en-CA');
  document.querySelector('#close-reconcile-dialog').click();

  document.querySelector('#open-import-button').click();
  assert.equal(document.querySelector('#import-dialog').hidden, false);
  const fileInput = document.querySelector('#transaction-import-form input[type="file"]');
  Object.defineProperty(fileInput, 'files', {value: [new dom.window.File(['data'], 'transactions.csv')]});
  fileInput.dispatchEvent(new dom.window.Event('change', {bubbles: true}));
  assert.equal(document.querySelector('#import-submit-button').disabled, false);
  document.querySelector('#transaction-import-form').dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
  await wait();
  await wait();
  assert.equal(calls.some(([url, options]) => url === '/api/model/transactions/import' && options.method === 'POST'), true);
  assert.match(document.querySelector('#toast').textContent, /1 transaction imported/);

  document.querySelector('#open-import-button').click();
  importMode = 'conflict';
  let confirmationMessage = '';
  dom.window.confirm = (message) => {
    confirmationMessage = message;
    return false;
  };
  document.querySelector('#transaction-import-form').dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
  await wait();
  assert.match(confirmationMessage, /Import anyway/);
  assert.doesNotMatch(confirmationMessage, /Reconciled period/);
  assert.match(document.querySelector('#import-result').textContent, /Import cancelled/);
  assert.equal(document.querySelector('#import-result').lang, 'en-CA');

  importMode = 'error';
  document.querySelector('#transaction-import-form').dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
  await wait();
  assert.match(document.querySelector('#import-result').textContent, /Unknown document/);
  assert.equal(document.querySelector('#import-result').lang, 'en-CA');
  assert.match(document.querySelector('#import-result a').textContent, /Open help/);
  document.querySelector('#close-import-dialog').click();
  assert.equal(document.querySelector('#import-dialog').hidden, true);
  dom.window.close();
});
