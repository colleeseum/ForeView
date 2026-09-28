import assert from 'node:assert/strict';
import test from 'node:test';

import {isSecurityAccount, ownerDetails} from '../../static/accounts-format.mjs';
import {formSignature} from '../../static/form-state.mjs';

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
