// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import test from 'node:test';
import {JSDOM} from 'jsdom';
import {configureTestLocalization} from './localization-fixture.mjs';
import {transactionsTableHtml} from '../../static/transactions/transactions-render.mjs';
import {formatDate, formatMoneyDollars} from '../../static/shared/locale-format.mjs';

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

test('transaction reads discard stale context and committed saves stay busy through refresh', async () => {
  const dom = installDom();
  const row = {transaction_date: '2026-01-10', description: 'Prior account evidence', amount: 10};
  let failed = '';
  let releaseRead;
  let holdRead = false;
  let writes = 0;
  globalThis.fetch = async (url, options = {}) => {
    if (options.method === 'POST') {
      writes++;
      return jsonResponse({imported: 1, files: 1, results: [], difference: 0});
    }
    const kind = url === '/api/model/accounts' ? 'accounts'
      : String(url).includes('/reconciliation') ? 'reconciliation'
        : String(url).includes('/import-history?') ? 'history' : 'transactions';
    if (kind === failed) return jsonResponse({}, false, 503);
    if (kind === 'accounts') return jsonResponse({accounts: [{id: 1, account_type: 'non_registered', asset_kind: 'account', name: 'Daily'}]});
    if (kind === 'history') return jsonResponse({imports: [{filename: 'Prior source.csv', row_count: 1}]});
    if (kind === 'reconciliation') return jsonResponse({reconciled_through: '2026-01-31', checkpoints: []});
    if (holdRead) await new Promise(resolve => {releaseRead = resolve;});
    return jsonResponse({transactions: [row]});
  };
  await import('../../static/transactions/transactions.mjs?recovery');
  await wait();
  await wait();
  const filter = document.querySelector('#transaction-account-filter');
  const table = document.querySelector('#transactions-table-content');
  const history = document.querySelector('#import-history-content');
  const error = document.querySelector('#transactions-error');
  const retry = document.querySelector('#transactions-retry');
  for (const kind of ['transactions', 'history', 'reconciliation', 'accounts']) {
    filter.value = '1';
    failed = kind;
    if (kind === 'accounts') retry.click();
    else filter.dispatchEvent(new dom.window.Event('change'));
    await wait();
    await wait();
    assert.equal(error.hidden, false, `${kind} failure must be reported`);
    if (kind === 'transactions' || kind === 'accounts') assert(!table.textContent.includes(row.description));
    if (kind === 'history' || kind === 'accounts') assert(!history.textContent.includes('Prior source.csv'));
    assert.equal(document.querySelector('#reconciliation-status').hidden, kind !== 'history' && kind !== 'transactions');
    failed = '';
    retry.click();
    await wait();
    await wait();
    assert.equal(error.hidden, true);
    assert(table.textContent.includes(row.description));
  }
  for (const type of ['import', 'reconcile']) {
    document.querySelector(type === 'import' ? '#open-import-button' : '#open-reconcile-button').click();
    const dialog = document.querySelector(`#${type}-dialog`);
    const form = document.querySelector(type === 'import' ? '#transaction-import-form' : '#reconcile-form');
    holdRead = true;
    form.dispatchEvent(new dom.window.Event('submit', {cancelable: true}));
    await wait();
    assert(dialog.open, 'Committed write must retain the busy dialog while refresh is pending');
    assert([...form.querySelectorAll('input, select, button')].every(node => node.disabled));
    form.dispatchEvent(new dom.window.Event('submit', {cancelable: true}));
    await wait();
    assert.equal(writes, type === 'import' ? 1 : 2);
    holdRead = false;
    releaseRead();
    await wait();
    await wait();
    assert.equal(dialog.open, false);
    assert.equal(error.hidden, true);
  }
  for (const type of ['import', 'reconcile']) {
    document.querySelector(type === 'import' ? '#open-import-button' : '#open-reconcile-button').click();
    failed = 'transactions';
    document.querySelector(type === 'import' ? '#transaction-import-form' : '#reconcile-form')
      .dispatchEvent(new dom.window.Event('submit', {cancelable: true}));
    await wait();
    await wait();
    assert.equal(document.querySelector(`#${type}-dialog`).open, false);
    assert.equal(document.querySelector('#toast').hidden, false);
    assert.equal(error.hidden, false);
    const committed = writes;
    failed = '';
    retry.click();
    await wait();
    await wait();
    assert.equal(writes, committed, 'Read-only retry must not repeat a committed mutation');
    assert.equal(error.hidden, true);
  }
  dom.window.close();
});

function installDom() {
  configureTestLocalization();
  const dom = new JSDOM(`<!doctype html><body>
    <button class="view-tab" data-type="non_registered"></button><button class="view-tab" data-type="tfsa"></button><button class="view-tab" data-type="rrsp"></button>
    <select id="transaction-account-filter"><option value="">All</option></select>
    <button id="open-reconcile-button"></button><button id="open-import-button"></button>
    <span id="breadcrumb-category"></span><span id="breadcrumb-account"></span><p id="reconciliation-status" hidden></p>
    <main class="fv-transactions"><select id="transaction-density"><option value="standard">Standard</option><option value="compact">Compact</option></select></main>
    <div id="transactions-error" hidden></div><button id="transactions-retry" hidden></button>
    <div id="transactions-table-content"></div><div id="import-history-content"></div>
    <dialog id="import-dialog" hidden><button id="close-import-dialog" data-dialog-close></button><h2 id="import-dialog-title"></h2><button id="import-inline-help"></button><details id="import-instructions"><summary>Help</summary><p id="import-dialog-description" data-default-text="Help"></p></details><ul id="import-file-review"></ul>
      <form id="transaction-import-form"><select id="transaction-account" name="account_id"></select><input name="files" type="file"><button id="import-submit-button" type="submit"></button></form><p id="import-result"></p>
    </dialog>
    <dialog id="import-confirm-dialog" hidden><p id="import-confirm-message"></p><button id="import-confirm-cancel" data-dialog-close></button><button id="import-confirm-continue"></button></dialog>
    <dialog id="reconcile-dialog" hidden><button id="close-reconcile-dialog" data-dialog-close></button>
      <form id="reconcile-form"><input id="reconcile-account-label"><input id="reconcile-date" name="date"><input id="reconcile-amount" name="amount"><button id="reconcile-submit-button" type="submit"></button></form><p id="reconcile-result"></p>
    </dialog><div id="toast" hidden></div>
  </body>`, {url: 'http://localhost/transactions?type=non_registered'});
  Object.assign(globalThis, {
    window: dom.window,
    document: dom.window.document,
    FormData: dom.window.FormData,
    File: dom.window.File,
    Option: dom.window.Option,
  });
  for (const dialog of dom.window.document.querySelectorAll('dialog')) {
    dialog.showModal = () => {dialog.open = true;};
    dialog.close = () => {dialog.open = false; dialog.dispatchEvent(new dom.window.Event('close'));};
  }
  return dom;
}

const wait = () => new Promise((resolve) => setTimeout(resolve, 0));
const jsonResponse = (data, ok = true, status = 200) => ({ok, status, text: async () => JSON.stringify(data), json: async () => data});

test('transactions module loads filters and reconciles the selected account', async () => {
  const dom = installDom();
  const guidance = document.querySelector('#import-dialog-description');
  guidance.innerHTML = '<span lang="fr-CA">Instructions traduites</span><span lang="en-CA">Provider fallback</span>';
  const originalGuidance = guidance.innerHTML;
  const attack = '<svg onload=alert(1)>';
  const calls = [];
  let importMode = 'success';
  let processedFiles = 0;
  let resolveImport;
  let failLoad = false;
  let reconcileError = false;
  let checkpointDate = null;
  globalThis.fetch = async (url, options = {}) => {
    calls.push([String(url), options]);
    if (url === '/api/model/accounts') return jsonResponse({accounts: [{id: 1, account_type: 'non_registered', asset_kind: 'account', account_number: 'A1', institution: 'Bank', name: 'Daily'}]});
    if (String(url).startsWith('/api/model/transactions?')) {
      if (failLoad) return jsonResponse({error: 'Synthetic unavailable'}, false, 503);
      return jsonResponse({transactions: [{transaction_date: '2026-09-01', institution: 'Bank', account_number: 'A1', description: attack, amount: 25, category: attack, balance_after: 125, combined_balance_after: 125}], opening_balances: []});
    }
    if (String(url).startsWith('/api/model/import-history?')) return jsonResponse({imports: [{imported_at: '2026-09-02', filename: attack, account_number: 'A1', row_count: 1}]});
    if (url === '/api/model/accounts/1/reconciliation') return jsonResponse({reconciled_through: '2026-09-01', checkpoints: checkpointDate ? [{status: 'needs_review', reconciled_through: checkpointDate, difference: -12.34}] : []});
    if (url === '/api/model/accounts/1/reconcile') {
      return reconcileError
        ? jsonResponse({error: 'Balance is invalid'}, false, 400)
        : jsonResponse({difference: 0, reconciled_through: '2026-09-01'});
    }
    if (url === '/api/model/transactions/import') {
      if (importMode.startsWith('both-')) {
        const flags = importMode === 'both-account' ? ['confirm_account_creation', 'confirm_reconciled'] : ['confirm_reconciled', 'confirm_account_creation'];
        const pending = flags.find(flag => !options.body.has(flag));
        if (pending) return jsonResponse({[pending]: true, error: 'Synthetic confirmation'}, false, 409);
      }
      if (importMode === 'account' && !options.body.has('confirm_account_creation')) return jsonResponse({confirm_account_creation: true, error: 'Synthetic new account', error_language: 'en-CA'}, false, 409);
      if (importMode === 'confirmed' && !options.body.has('confirm_reconciled')) return jsonResponse({confirm_reconciled: true}, false, 409);
      if (importMode === 'slow') return new Promise(resolve => {resolveImport = resolve;});
      if (importMode === 'conflict') return jsonResponse({confirm_reconciled: true, error: 'Reconciled period', files_imported: processedFiles}, false, 409);
      if (importMode === 'error') return jsonResponse({error: 'Unknown document', help_url: '/help'}, false, 400);
      return jsonResponse({imported: 1, files: 1, results: []});
    }
    throw new Error(`Unexpected fetch: ${url}`);
  };

  await import('../../static/transactions/transactions.mjs');
  await wait();
  await wait();

  const table = document.querySelector('#transactions-table-content');
  assert.ok(table.textContent.includes(formatDate('2026-09-01')));
  assert.equal(table.innerHTML.includes(attack), false);
  assert.equal(document.querySelector('#import-history-content').innerHTML.includes(attack), false);

  const filter = document.querySelector('#transaction-account-filter');
  filter.value = '1';
  filter.dispatchEvent(new dom.window.Event('change'));
  await wait();
  assert.match(document.querySelector('#reconciliation-status').textContent, /Reconciled through/);

  for (const locale of ['en-CA', 'fr-CA']) {
    configureTestLocalization(locale);
    for (const value of ['2026-01-31', 'malformed evidence']) {
      checkpointDate = value;
      filter.dispatchEvent(new dom.window.Event('change'));
      await wait();
      await wait();
      const status = document.querySelector('#reconciliation-status');
      assert.equal(status.hidden, false);
      assert.ok(status.classList.contains('error'));
      assert.ok(status.textContent.includes(value === '2026-01-31' ? formatDate(value) : value));
      assert.ok(status.textContent.includes(formatMoneyDollars(-12.34)));
      assert.equal((status.textContent.match(/\$/g) || []).length, 1);
    }
  }
  checkpointDate = null;
  configureTestLocalization();

  document.querySelector('#open-reconcile-button').click();
  document.querySelector('#reconcile-date').value = '2026-09-01';
  document.querySelector('#reconcile-amount').value = '125';
  document.querySelector('#reconcile-form').dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
  await wait();
  await wait();
  assert.equal(document.querySelector('#reconcile-dialog').hidden, true);
  assert.equal(calls.some(([url, options]) => url === '/api/model/accounts/1/reconcile' && options.method === 'POST'), true);
  assert.deepEqual(JSON.parse(calls.find(([url]) => url === '/api/model/accounts/1/reconcile')[1].body), {date: '2026-09-01', amount: '125'});
  for (const locale of ['en-CA', 'fr-CA']) {
    configureTestLocalization(locale);
    document.querySelector('#open-reconcile-button').click();
    document.querySelector('#reconcile-form').dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
    await wait();
    await wait();
    const toast = document.querySelector('#toast').textContent;
    assert.ok(toast.includes(formatDate('2026-09-01')));
    assert.ok(!toast.includes('2026-09-01'));
  }
  configureTestLocalization();

  document.querySelector('#open-reconcile-button').click();
  reconcileError = true;
  document.querySelector('#reconcile-form').dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
  await wait();
  assert.match(document.querySelector('#reconcile-result').textContent, /Balance is invalid/);
  assert.equal(document.querySelector('#reconcile-result').lang, 'en-CA');
  document.querySelector('#close-reconcile-dialog').click();

  document.querySelector('#open-import-button').click();
  assert.equal(guidance.innerHTML, originalGuidance);
  assert.equal(document.querySelector('#import-dialog').hidden, false);
  const fileInput = document.querySelector('#transaction-import-form input[type="file"]');
  Object.defineProperty(fileInput, 'files', {value: [new dom.window.File(['data'], 'transactions.csv')]});
  fileInput.dispatchEvent(new dom.window.Event('change', {bubbles: true}));
  assert.equal(document.querySelector('#import-submit-button').disabled, false);
  assert.match(document.querySelector('#import-file-review').textContent, /transactions.csv/);
  document.querySelector('#transaction-import-form').dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
  await wait();
  await wait();
  assert.equal(calls.some(([url, options]) => url === '/api/model/transactions/import' && options.method === 'POST'), true);
  assert.match(document.querySelector('#toast').textContent, /1 transaction imported/);

  document.querySelector('#open-import-button').click();
  assert.equal(guidance.innerHTML, originalGuidance);
  importMode = 'conflict';
  document.querySelector('#transaction-import-form').dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
  await wait();
  const confirmationMessage = document.querySelector('#import-confirm-message').textContent;
  assert.match(confirmationMessage, /Import anyway/);
  assert.doesNotMatch(confirmationMessage, /Reconciled period/);
  document.querySelector('#import-confirm-cancel').click();
  await wait();
  assert.match(document.querySelector('#import-result').textContent, /Import cancelled/);
  assert.equal(document.querySelector('#import-result').lang, 'en-CA');
  processedFiles = 1;
  document.querySelector('#transaction-import-form').dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
  await wait();
  document.querySelector('#import-confirm-cancel').click();
  await wait();
  assert.match(document.querySelector('#import-result').textContent, /Import stopped.*Earlier files.*already been processed/);

  for (const mode of ['account', 'confirmed', 'both-account', 'both-reconciled']) {
    importMode = mode;
    document.querySelector('#transaction-import-form').dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
    await wait();
    assert.equal(document.querySelector('#import-confirm-dialog').open, true);
    document.querySelector('#import-confirm-continue').click();
    await wait();
    if (mode.startsWith('both-')) {
      assert.equal(document.querySelector('#import-confirm-dialog').open, true);
      document.querySelector('#import-confirm-continue').click();
      await wait();
    }
    await wait();
    const form = calls.filter(([url]) => url === '/api/model/transactions/import').at(-1)[1].body;
    const flags = mode.startsWith('both-') ? ['confirm_account_creation', 'confirm_reconciled']
      : [mode === 'account' ? 'confirm_account_creation' : 'confirm_reconciled'];
    for (const flag of flags) assert.equal(form.get(flag), '1');
    assert.equal(form.get('account_id'), '1');
    assert.equal(document.querySelector('#import-dialog').open, false);
    document.querySelector('#open-import-button').click();
  }
  importMode = 'slow';
  const form = document.querySelector('#transaction-import-form');
  const before = calls.filter(([url]) => url === '/api/model/transactions/import').length;
  for (let index = 0; index < 2; index++) form.dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
  await wait();
  assert.equal(calls.filter(([url]) => url === '/api/model/transactions/import').length, before + 1);
  assert.equal(form.getAttribute('aria-busy'), 'true');
  const cancel = new dom.window.Event('cancel', {cancelable: true});
  document.querySelector('#import-dialog').dispatchEvent(cancel);
  assert.equal(cancel.defaultPrevented, true);
  resolveImport(jsonResponse({imported: 0, duplicates: 2, files: 2}));
  await wait();
  await wait();
  assert.equal(form.getAttribute('aria-busy'), 'false');
  assert.match(document.querySelector('#toast').textContent, /Duplicate rows skipped: 2/);

  failLoad = true;
  filter.dispatchEvent(new dom.window.Event('change'));
  await wait();
  assert.equal(document.querySelector('#transactions-error').hidden, false);
  assert.equal(table.getAttribute('aria-busy'), 'false');
  failLoad = false;
  document.querySelector('#transactions-retry').click();
  await wait();
  await wait();
  assert.equal(document.querySelector('#transactions-error').hidden, true);
  assert.equal(filter.value, '1');

  document.querySelector('#open-import-button').click();
  importMode = 'error';
  document.querySelector('#transaction-import-form').dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
  await wait();
  assert.match(document.querySelector('#import-result').textContent, /Unknown document/);
  assert.equal(document.querySelector('#import-result').lang, 'en-CA');
  assert.match(document.querySelector('#import-result a').textContent, /Open help/);
  document.querySelector('#import-result a').click();
  assert.equal(document.querySelector('#import-instructions').open, true);
  document.querySelector('#close-import-dialog').click();
  assert.equal(document.querySelector('#import-dialog').hidden, true);
  dom.window.close();
});
