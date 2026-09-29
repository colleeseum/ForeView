import assert from 'node:assert/strict';
import test from 'node:test';
import {JSDOM} from 'jsdom';

function installDom() {
  const dom = new JSDOM(`<!doctype html><body>
    <button class="view-tab" data-view="non_registered">Non-registered</button>
    <button class="view-tab" data-view="tfsa">TFSA</button>
    <button class="view-tab" data-view="rrsp">RRSP</button>
    <button class="view-tab" data-view="real_estate">Real estate</button>
    <button id="reload-assets"></button>
    <section id="accounts-table" class="view-panel"><div id="accounts-table-content"></div></section>
    <div id="account-dialog" hidden><button id="close-account-dialog"></button><h2 id="account-dialog-title"></h2><p id="account-dialog-message"></p>
      <form id="account-dialog-form">
        <input name="account_number"><input name="institution"><input name="name">
        <select name="category"><option value="non_registered">Non-registered</option><option value="tfsa">TFSA</option><option value="rrsp">RRSP</option></select>
        <input name="balance_date"><input name="balance_amount"><input name="interest_rate">
        <div id="dialog-owner-fields"></div><button type="submit">Save</button>
      </form>
    </div>
    <div id="subaccount-dialog" hidden><button id="close-subaccount-dialog"></button><h2 id="subaccount-dialog-title"></h2><p id="subaccount-dialog-message"></p>
      <form id="subaccount-dialog-form">
        <select id="subaccount-parent" name="parent_account_id"></select><input name="account_number"><input name="name">
        <input name="start_date"><input name="maturity_date"><input name="principal"><input name="maturity_value">
        <input name="redeemable" type="checkbox"><input name="balance_date"><input name="balance_amount"><input name="interest_rate">
        <button type="submit">Save</button>
      </form>
    </div>
    <div id="real-estate-dialog" hidden><button id="close-real-estate-dialog"></button><h2 id="real-estate-dialog-title"></h2><p id="real-estate-dialog-message"></p>
      <form id="real-estate-dialog-form">
        <input name="name"><input name="property_type"><input name="estimated_value"><input name="valuation_date">
        <input name="acb"><input name="principal_residence" type="checkbox"><div id="real-estate-owner-fields"></div>
        <p id="real-estate-owner-total"></p><button type="submit">Save</button>
      </form>
    </div>
  `, {url: 'http://localhost/accounts?tab=non_registered'});
  Object.assign(globalThis, {
    window: dom.window,
    document: dom.window.document,
    FormData: dom.window.FormData,
    Option: dom.window.Option,
  });
  dom.window.document.querySelectorAll('form').forEach((form) => {
    [...form.elements].filter((field) => field.name).forEach((field) => {
      Object.defineProperty(form, field.name, {value: field, configurable: true});
    });
  });
  return dom;
}

function response(data, ok = true) {
  return {ok, status: ok ? 200 : 400, json: async () => data};
}

test('assets module renders account, portfolio, GIC, and real-estate views', async () => {
  const dom = installDom();
  const attack = '<img src=x onerror=alert(1)>';
  const writes = [];
  let failNextWrite = false;
  const accounts = [
    {id: 1, asset_kind: 'account', account_type: 'non_registered', institution: 'Questrade', account_number: 'A1', name: attack, latest_amount: 120, rollup_amount: 120, owner_details: '1:1'},
    {id: 2, parent_account_id: 1, asset_kind: 'gic', account_type: 'non_registered', institution: 'Questrade', account_number: 'G1', name: 'Term deposit', latest_amount: 20, maturity_date: '2028-01-01', interest_rate: 0.04, redeemable: false},
  ];
  globalThis.fetch = async (url, options = {}) => {
    if (url === '/api/model/accounts' && !options.method) return response({accounts, category_totals: [{type: 'non_registered', count: 1, gic_count: 1, total: 120}]});
    if (url === '/api/model/holdings' && !options.method) return response({holdings: [{account_id: 1, fund_code: attack, fund_name: 'Fund', asset_class: 'Security', units: 1, unit_price: 100, market_value: 100, allocation_pct: 100, valuation_date: '2026-09-28'}]});
    if (url === '/api/model/real-estate' && !options.method) return response({assets: [{id: 9, name: attack, property_type: 'Land', estimated_value: 50000, acb: 10000, principal_residence: false, valuation_date: '2026-01-01', owners: [{person_id: 1, name: attack, share: 1}]}]});
    if (url === '/api/model/people' && !options.method) return response({people: [{id: 1, name: attack}, {id: 2, name: 'Second owner'}]});
    if (options.method) {
      writes.push({url, options});
      if (failNextWrite) {
        failNextWrite = false;
        return response({error: 'Save failed'}, false);
      }
      return response({});
    }
    throw new Error(`Unexpected fetch: ${url}`);
  };

  await import('../../static/accounts.mjs');
  await new Promise((resolve) => setTimeout(resolve, 0));

  const content = document.querySelector('#accounts-table-content');
  assert.match(content.textContent, /Questrade/);
  assert.equal(content.innerHTML.includes(attack), false);
  content.querySelector('[data-toggle-portfolio="1"]').click();
  assert.equal(content.querySelector('#portfolio-1').hidden, false);
  content.querySelector('[data-toggle-portfolio="1"]').click();
  assert.equal(content.querySelector('#portfolio-1').hidden, true);

  content.querySelector('[data-edit-account="1"]').click();
  const accountForm = document.querySelector('#account-dialog-form');
  assert.equal(document.querySelector('#account-dialog-title').textContent, 'Edit account');
  accountForm.elements.name.value = 'Updated';
  accountForm.dispatchEvent(new dom.window.Event('input', {bubbles: true}));
  assert.equal(accountForm.querySelector('button[type="submit"]').disabled, false);
  accountForm.dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(writes.some(({url, options}) => url === '/api/model/accounts/1' && options.method === 'PUT'), true);

  content.querySelector('[data-edit-account="2"]').click();
  const gicForm = document.querySelector('#subaccount-dialog-form');
  assert.equal(gicForm.elements.account_number.value, 'G1');
  gicForm.dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(writes.some(({url, options}) => url === '/api/model/accounts/2' && options.method === 'PUT'), true);

  content.querySelector('[data-add-account-type="non_registered"]').click();
  assert.equal(document.querySelector('#account-dialog-title').textContent, 'Add account');
  document.dispatchEvent(new dom.window.KeyboardEvent('keydown', {key: 'Escape'}));
  assert.equal(document.querySelector('#account-dialog').hidden, true);
  content.querySelector('[data-add-account-type="non_registered"]').click();
  accountForm.elements.institution.value = 'New bank';
  accountForm.dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(writes.some(({url, options}) => url === '/api/model/accounts' && options.method === 'POST'), true);

  content.querySelector('[data-add-account-type="non_registered"]').click();
  failNextWrite = true;
  accountForm.dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.match(document.querySelector('#account-dialog-message').textContent, /Save failed/);

  content.querySelector('[data-add-subaccount="1"]').click();
  assert.equal(document.querySelector('#subaccount-dialog-title').textContent, 'Add GIC');
  failNextWrite = true;
  gicForm.dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.match(document.querySelector('#subaccount-dialog-message').textContent, /Save failed/);
  assert.equal(gicForm.querySelector('button[type="submit"]').disabled, false);

  document.querySelector('[data-view="real_estate"]').click();
  assert.match(content.textContent, /Land/);
  assert.equal(content.innerHTML.includes(attack), false);

  content.querySelector('[data-edit-real-estate="9"]').click();
  assert.equal(document.querySelector('#real-estate-dialog').hidden, false);
  assert.equal(document.querySelector('#real-estate-dialog-form').elements.name.value, attack);
  const realEstateForm = document.querySelector('#real-estate-dialog-form');
  realEstateForm.elements.estimated_value.value = '51000';
  realEstateForm.dispatchEvent(new dom.window.Event('input', {bubbles: true}));
  realEstateForm.dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(writes.some(({url, options}) => url === '/api/model/real-estate/9' && options.method === 'PUT'), true);

  content.querySelector('[data-add-real-estate]').click();
  assert.equal(document.querySelector('#real-estate-dialog-title').textContent, 'Add real-estate asset');

  const ownerChecks = [...document.querySelectorAll('#real-estate-owner-fields [data-owner-id]')];
  ownerChecks[0].click();
  ownerChecks[1].click();
  assert.equal(document.querySelector('#real-estate-owner-fields [data-owner-share="1"]').value, '50');
  assert.equal(document.querySelector('#real-estate-owner-fields [data-owner-share="2"]').value, '50');
  ownerChecks[1].click();
  assert.equal(document.querySelector('#real-estate-owner-fields [data-owner-share="1"]').value, '100');
  failNextWrite = true;
  realEstateForm.dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.match(document.querySelector('#real-estate-dialog-message').textContent, /Save failed/);
  assert.equal(realEstateForm.querySelector('button[type="submit"]').disabled, false);

  const {renderAssets} = await import('../../static/accounts-render.mjs');
  const {assetState} = await import('../../static/accounts-state.mjs');
  assetState.view = 'non_registered';
  assetState.accounts = [];
  renderAssets({openAccount: () => {}, openGic: () => {}});
  assert.match(content.textContent, /No accounts yet/);

  assetState.accounts = [{id: 3, asset_kind: 'account', account_type: 'tfsa', institution: 'Bank', account_number: '', name: '', latest_amount: null, rollup_amount: null}];
  assetState.categoryTotals = [];
  assetState.holdings = [];
  assetState.view = 'tfsa';
  let openedAccount = null;
  renderAssets({openAccount: (id) => { openedAccount = id; }, openGic: () => {}});
  content.querySelector('[data-edit-account="3"]').click();
  assert.equal(openedAccount, 3);

  assetState.realEstateAssets = [];
  assetState.view = 'real_estate';
  renderAssets({openAccount: () => {}, openGic: () => {}});
  assert.match(content.textContent, /No real-estate assets yet/);

  dom.window.close();
});
