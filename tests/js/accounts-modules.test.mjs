// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import test from 'node:test';
import {
  escapeHtml,
  htmlWithLanguageSpans,
  languageSpan,
  sourceTextSpan,
} from '../../static/html.mjs';
import {createLatestRequestGate} from '../../static/latest-request.mjs';

import {isSecurityAccount, money, ownerDetails} from '../../static/accounts-format.mjs';
import {formSignature, showError} from '../../static/form-state.mjs';
import {editableAccountValues} from '../../static/setup-values.mjs';
import {runButtonAction} from '../../static/button-action.mjs';
import {
  cashFlowCategoryLabel,
  importHistoryHtml,
  transactionsTableHtml,
} from '../../static/transactions-render.mjs';
import {importMessage} from '../../static/transaction-import-message.mjs';
import {configureTestLocalization} from './localization-fixture.mjs';

configureTestLocalization();

test('security accounts are classified without coupling the renderer', () => {
  assert.equal(isSecurityAccount({asset_kind: 'account', institution: ' Sun Life '}), true);
  assert.equal(isSecurityAccount({asset_kind: 'gic', institution: 'Sun Life'}), false);
  assert.equal(isSecurityAccount({asset_kind: 'account', institution: 'RBC'}), false);
});

test('owner details are converted from the API read model', () => {
  assert.deepEqual(ownerDetails({owner_details: '12:0.5,19:0.5'}), [
    {person_id: 12, share: 0.5},
    {person_id: 19, share: 0.5},
  ]);
  assert.deepEqual(ownerDetails({owner_details: ''}), []);
});

test('money and error formatting cover optional values', () => {
  assert.equal(money(null, true), '');
  assert.equal(money(null), '0.00');
  const classes = new Set();
  const target = {textContent: '', classList: {add: (value) => classes.add(value)}};
  showError(target, new Error('broken'));
  assert.equal(target.textContent, 'broken');
  showError(target, 'plain failure');
  assert.equal(target.textContent, 'plain failure');
  assert.equal(classes.has('error'), true);
});

test('form signatures include checkbox state and additional components', () => {
  const form = {
    elements: [
      {name: 'name', type: 'text', value: 'Savings'},
      {name: 'redeemable', type: 'checkbox', checked: true},
      {name: '', type: 'button', value: 'ignored'},
    ],
  };
  assert.equal(
    formSignature(form, ['owner:12:true:100']),
    'name:Savings|redeemable:true|owner:12:true:100',
  );
});
test('escapeHtml makes imported and user-entered text inert', () => {
  assert.equal(escapeHtml(`<img src=x onerror="alert('x')">`), '&lt;img src=x onerror=&quot;alert(&#39;x&#39;)&quot;&gt;');
  assert.equal(languageSpan('<unsafe>'), '<span lang="en-CA">&lt;unsafe&gt;</span>');
  assert.equal(sourceTextSpan('<source>'), '<span lang="">&lt;source&gt;</span>');
  assert.equal(sourceTextSpan('Description', 'fr-CA'), '<span lang="fr-CA">Description</span>');
  assert.equal(
    htmlWithLanguageSpans(
      ({message}) => `<img src=x onerror="bad"> Error: ${message}`,
      {message: '<unsafe>'},
    ),
    '&lt;img src=x onerror=&quot;bad&quot;&gt; Error: <span lang="en-CA">&lt;unsafe&gt;</span>',
  );
});

test('latest request gate rejects an older response', () => {
  const gate = createLatestRequestGate();
  const first = gate.begin();
  const second = gate.begin();
  assert.equal(first(), false);
  assert.equal(second(), true);
});

test('setup preserves a GIC reference and quoted account fields', () => {
  assert.deepEqual(editableAccountValues({
    institution: 'Bank "One"',
    name: 'Five-year "special"',
    account_number: 'GIC-123',
  }), {
    institution: 'Bank "One"',
    name: 'Five-year "special"',
    account_number: 'GIC-123',
  });
});

test('button action restores the clicked control after failure', async () => {
  const button = {disabled: false, textContent: 'Re-fetch'};
  await assert.rejects(
    runButtonAction(button, 'Re-fetching...', async () => { throw new Error('failed'); }),
    /failed/,
  );
  assert.deepEqual(button, {disabled: false, textContent: 'Re-fetch'});
});

test('transaction and import-history renderers escape external text', () => {
  const attack = '<img src=x onerror=alert(1)>';
  const table = transactionsTableHtml([{
    transaction_date: attack,
    institution: attack,
    account_number: '1',
    description: attack,
    amount: '1.00',
    category: attack,
  }], [], false);
  const history = importHistoryHtml([{
    imported_at: attack,
    filename: attack,
    account_number: attack,
    row_count: 1,
    reconciliation_status: attack,
  }]);
  assert.equal(table.includes(attack), false);
  assert.equal(history.includes(attack), false);
  assert.match(table, /&lt;img/);
  assert.match(history, /&lt;img/);
});

test('transaction renderer covers empty, GIC, opening, and filtered rows', () => {
  assert.match(transactionsTableHtml([], [], false), /No transactions yet/);
  assert.match(importHistoryHtml([]), /No imports yet/);
  const html = transactionsTableHtml([{
    transaction_date: '2026-01-02',
    asset_kind: 'gic',
    parent_institution: 'Bank',
    parent_account_number: 'A1',
    account_name: 'Term',
    description: 'Opening',
    balance_after: null,
    is_opening_balance: true,
  }, {
    transaction_date: '2026-01-02',
    account_name: 'Cash account',
    description: 'Deposit',
    amount: 10,
    balance_after: 10,
  }], [], true);
  assert.match(html, /GIC · Bank · A1 · Term/);
  assert.match(html, /Balance anchor/);
  assert.match(html, /Unclassified/);
  assert.match(html, /opening-balance-row/);
  assert.equal(html.includes('Combined balance'), false);
  assert.match(importHistoryHtml([{imported_at: '', filename: '', account_number: '', row_count: 0, reconciliation_status: 'reconciled'}]), /Reconciliation: Reconciled/);
});

test('transaction renderer localizes normalized cash-flow categories with a raw fallback', () => {
  configureTestLocalization('fr-CA');
  assert.match(money(1234.5), /1.*234,50/);
  assert.equal(cashFlowCategoryLabel('Interest'), 'Intérêt');
  assert.equal(cashFlowCategoryLabel(' withdrawal '), 'Retrait');
  assert.equal(cashFlowCategoryLabel('grant'), 'Subvention');
  assert.equal(cashFlowCategoryLabel('Provider-specific'), 'Provider-specific');
  const html = transactionsTableHtml([{
    transaction_date: '2026-01-02',
    description: 'Interest payment',
    amount: 10,
    category: 'Interest',
  }], [], true);
  assert.match(html, /Intérêt/);
  assert.doesNotMatch(html, />Interest<\/td>/);
  assert.equal(html.includes('<span lang="">Interest payment</span>'), true);
  assert.match(
    importMessage({results: [{reconciliation_status: 'difference', difference: 4.5}]}),
    /4,50/,
  );
  configureTestLocalization();
});

test('reconciliation history statuses follow the browser locale', () => {
  configureTestLocalization('fr-CA');
  assert.match(
    importHistoryHtml([{imported_at: '', filename: '', account_number: '', row_count: 0, reconciliation_status: 'needs_review'}]),
    /Rapprochement : À vérifier/,
  );
  const accounts = transactionsTableHtml([{
    transaction_date: '2026-01-02', asset_kind: 'gic', parent_institution: 'Banque',
    parent_account_number: 'A1', account_name: 'Terme', description: 'Intérêt', amount: 1,
  }, {
    transaction_date: '2026-01-01', institution: 'Banque', account_number: 'A2',
    description: 'Dépôt', amount: 1,
  }], [], false);
  assert.match(accounts, /CPG · Banque/);
  assert.match(accounts, /Encaisse · Banque/);
  configureTestLocalization();
});

test('setup values normalize missing optional fields', () => {
  assert.deepEqual(editableAccountValues({}), {institution: '', name: '', account_number: ''});
});

test('transaction import summaries cover reconciliation and statement outcomes', () => {
  assert.match(importMessage({results: [{reconciliation_status: 'reconciled', csv_transaction_count: '1'}]}), /1 CSV transaction matched/);
  assert.match(importMessage({results: [{reconciliation_status: 'reconciled', csv_transaction_count: 2}]}), /2 CSV transactions/);
  assert.match(importMessage({results: [{reconciliation_status: 'no_matching_transactions'}]}), /no CSV transactions/);
  assert.match(importMessage({results: [{reconciliation_status: 'difference', difference: 4.5}]}), /\$4.50/);
  assert.match(importMessage({results: [{document_type: 'statement', imported: 1, gics: 1}]}), /1 interest entry and 1 CPG record\./);
  assert.match(importMessage({results: [{document_type: 'maturity_notice', imported: 2, gics: 2}]}), /2 interest entries and 2 CPG records/);
  assert.equal(importMessage({imported: 1, files: 1}), '1 transaction imported from 1 file.');
  assert.equal(importMessage({imported: 2, files: 2}), '2 transactions imported from 2 files.');
});
