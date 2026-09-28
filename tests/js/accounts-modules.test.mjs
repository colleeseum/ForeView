import assert from 'node:assert/strict';
import test from 'node:test';
import {escapeHtml} from '../../static/html.mjs';
import {createLatestRequestGate} from '../../static/latest-request.mjs';

import {isSecurityAccount, ownerDetails} from '../../static/accounts-format.mjs';
import {formSignature} from '../../static/form-state.mjs';
import {editableAccountValues} from '../../static/setup-values.mjs';
import {runButtonAction} from '../../static/button-action.mjs';
import {importHistoryHtml, transactionsTableHtml} from '../../static/transactions-render.mjs';

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
