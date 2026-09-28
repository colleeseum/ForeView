import assert from 'node:assert/strict';
import test from 'node:test';
import {JSDOM} from 'jsdom';

function form(id, fields) {
  return `<form id="${id}">${fields}<button type="submit" disabled>Save</button></form>`;
}

function installDom() {
  const dom = new JSDOM(`<!doctype html><body>
    <p id="setup-message"></p><ul id="people-list"></ul><div id="accounts-list"></div><div id="owner-fields"></div>
    <button class="setup-tab" data-tab="people-panel"></button><section id="people-panel" class="setup-panel"></section>
    ${form('person-form', '<input name="name"><input name="birth_date">')}
    ${form('account-form', '<input name="institution"><input name="account_number"><input name="name"><select name="category"><option value="tfsa">TFSA</option></select>')}
    ${form('balance-form', '<select id="balance-account" name="account_id"></select><input name="date"><input name="amount">')}
    ${form('gic-form', '<select id="gic-account" name="account_id"></select><input name="name"><input name="account_number"><input name="redeemable" type="checkbox">')}
    ${form('scenario-form', '<input name="name">')}
  </body>`, {url: 'http://localhost/setup'});
  Object.assign(globalThis, {
    window: dom.window,
    document: dom.window.document,
    FormData: dom.window.FormData,
    Option: dom.window.Option,
  });
  dom.window.document.querySelectorAll('form').forEach((currentForm) => {
    [...currentForm.elements].filter((field) => field.name).forEach((field) => {
      Object.defineProperty(currentForm, field.name, {value: field, configurable: true});
    });
  });
  return dom;
}

const wait = () => new Promise((resolve) => setTimeout(resolve, 0));

test('setup renders safely and submits each configuration form', async () => {
  const dom = installDom();
  const attack = '<img src=x onerror=alert(1)>';
  const requests = [];
  const people = [{id: 1, name: attack, birth_date: '1970-01-01'}];
  const accounts = [
    {id: 1, asset_kind: 'account', account_type: 'tfsa', institution: 'Bank', account_number: 'A1', name: 'Savings', owners: attack},
    {id: 2, asset_kind: 'gic', account_type: 'tfsa', institution: 'Bank', account_number: 'REF-"2"', name: 'GIC "special"', owners: 'Owner'},
  ];
  globalThis.fetch = async (url, options = {}) => {
    requests.push({url, options});
    if (url === '/api/model/people' && !options.method) return {ok: true, json: async () => ({people})};
    if (url === '/api/model/accounts' && !options.method) return {ok: true, json: async () => ({accounts})};
    return {ok: true, json: async () => ({})};
  };

  await import('../../static/setup.mjs');
  await wait();
  await wait();

  assert.equal(document.body.innerHTML.includes(attack), false);
  const gicReference = document.querySelector('[data-account-id="2"][data-account-field="account_number"]');
  assert.equal(gicReference.value, 'REF-"2"');
  gicReference.value = 'REF-3';
  gicReference.dispatchEvent(new dom.window.Event('input', {bubbles: true}));
  const saveAccount = document.querySelector('[data-save-account="2"]');
  assert.equal(saveAccount.hidden, false);
  saveAccount.click();
  await wait();
  assert.equal(requests.some(({url, options}) => url === '/api/model/accounts/2' && options.method === 'PUT' && JSON.parse(options.body).account_number === 'REF-3'), true);

  const submissions = [
    ['person-form', '/api/model/people'],
    ['account-form', '/api/model/accounts'],
    ['balance-form', '/api/model/accounts/1/balance'],
    ['gic-form', '/api/model/accounts/1/gics'],
    ['scenario-form', '/api/model/scenarios'],
  ];
  document.querySelector('#account-form [name="institution"]').value = 'Bank';
  document.querySelector('#owner-fields input[type="checkbox"]').checked = true;
  document.querySelector('#balance-account').value = '1';
  document.querySelector('#gic-account').value = '1';
  for (const [formId, expectedUrl] of submissions) {
    const currentForm = document.querySelector(`#${formId}`);
    currentForm.dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
    await wait();
    assert.equal(requests.some(({url, options}) => url === expectedUrl && options.method === 'POST'), true, formId);
  }

  assert.match(document.querySelector('#setup-message').textContent, /created|added|saved/i);
  dom.window.close();
});
