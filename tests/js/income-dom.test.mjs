import assert from 'node:assert/strict';
import test from 'node:test';

import {JSDOM} from 'jsdom';

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

function installDom() {
  const fields = [
    'employment_income', 'bonus', 'other_income', 'cpp_qpp', 'ei', 'qpip',
    'rrsp_contribution', 'rrsp_deduction', 'federal_tax', 'provincial_tax',
  ].map((name) => `<input name="${name}" value="0">`).join('');
  const dom = new JSDOM(`<!doctype html><body>
    <div id="income-tabs"></div><p id="income-message"></p><div id="income-history"></div>
    <button id="income-add"></button><button id="income-import"></button>
    <div id="income-dialog-backdrop" hidden></div><button id="income-dialog-close"></button>
    <form id="income-form"><input name="tax_year" value="2025"><select name="province_of_employment"><option value=""></option><option value="ON">ON</option><option value="QC">QC</option></select>${fields}<select name="source"><option>T1</option><option>UFile T1</option><option>Manual</option></select><button type="submit"></button></form>
    <output id="income-salary-rate"></output>
    <div id="ufile-dialog-backdrop" hidden></div><button id="ufile-dialog-close"></button>
    <p id="ufile-person"></p>
    <form id="ufile-form"><input id="income-import-file" name="file" type="file"><button id="income-import-preview" type="submit" disabled></button></form>
  </body>`, {url: 'http://localhost/income'});
  Object.assign(globalThis, {
    window: dom.window,
    document: dom.window.document,
    FormData: dom.window.FormData,
  });
  return dom;
}

function annualRecord(overrides = {}) {
  return {
    id: 4, person_id: 1, year: 2025, employment_income: '100000.00',
    province_of_employment: 'ON', payroll_plan: 'CPP',
    bonus: '5000.00', salary_rate: '95000.00', other_income: '1000.00',
    gross_income: '101000.00', cpp_qpp: '4000.00', ei: '900.00', qpip: '400.00',
    rrsp_contribution: '10000.00', rrsp_deduction: '10000.00',
    federal_tax: '12000.00', provincial_tax: '13000.00',
    disposable_income: '60700.00', source: 'UFile T1', ...overrides,
  };
}

test('income screen previews a UFile return and saves only after review', async () => {
  const dom = installDom();
  const calls = [];
  let saved = false;
  globalThis.fetch = async (url, options = {}) => {
    calls.push({url: String(url), options});
    if (url === '/api/model/people') {
      return {ok: true, json: async () => ({people: [{id: 1, name: 'Alex'}, {id: 2, name: '<b>Jordan</b>'}]})};
    }
    if (String(url).startsWith('/api/income?')) {
      return {ok: true, json: async () => ({records: saved ? [annualRecord()] : [annualRecord(), annualRecord({id: 3, year: 2024, employment_income: '90000.00'})]})};
    }
    if (url === '/api/income/import/preview') {
      return {ok: true, json: async () => annualRecord({year: 2024, province_of_employment: 'QC', taxpayer_name: 'Alex', source_name: 'UFile T1 PDF', source_version: '0.1.0'})};
    }
    if (String(url).startsWith('/api/income/people/')) {
      saved = true;
      return {ok: true, json: async () => annualRecord()};
    }
    throw new Error(`Unexpected URL ${url}`);
  };

  await import(`../../static/income.mjs?main=${Date.now()}`);
  await tick(); await tick();
  assert.match(document.querySelector('#income-message').textContent, /2 annual records/);
  assert.match(document.querySelector('#income-history').textContent, /2025 Latest/);
  assert.match(document.querySelector('#income-history').textContent, /2024/);
  assert.equal(document.querySelector('#income-dialog-backdrop').hidden, true);
  assert.equal(document.body.innerHTML.includes('<b>Jordan</b>'), false);

  document.querySelector('[data-edit-year="2024"]').click();
  assert.equal(document.querySelector('#income-dialog-backdrop').hidden, false);
  assert.equal(document.querySelector('[name="tax_year"]').value, '2024');
  assert.equal(document.querySelector('[name="tax_year"]').disabled, true);
  assert.equal(document.querySelector('[name="province_of_employment"]').value, 'ON');
  document.querySelector('#income-dialog-close').click();
  assert.equal(document.querySelector('#income-dialog-backdrop').hidden, true);
  document.querySelector('#income-add').click();
  assert.equal(document.querySelector('[name="tax_year"]').disabled, false);
  document.querySelector('#income-dialog-close').click();

  document.querySelector('#income-import').click();
  assert.equal(document.querySelector('#ufile-dialog-backdrop').hidden, false);
  assert.match(document.querySelector('#ufile-person').textContent, /Alex/);
  const importFile = document.querySelector('#income-import-file');
  const importPreview = document.querySelector('#income-import-preview');
  assert.equal(importPreview.disabled, true);
  Object.defineProperty(importFile, 'files', {
    configurable: true,
    value: [new dom.window.File(['pdf'], 'return.pdf', {type: 'application/pdf'})],
  });
  importFile.dispatchEvent(new dom.window.Event('change', {bubbles: true}));
  assert.equal(importPreview.disabled, false);
  document.querySelector('#ufile-dialog-close').click();
  assert.equal(document.querySelector('#ufile-dialog-backdrop').hidden, true);
  document.querySelector('#income-import').click();
  document.querySelector('#ufile-form').dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
  await tick(); await tick();
  assert.equal(document.querySelector('[name="tax_year"]').value, '2024');
  assert.equal(document.querySelector('#income-dialog-backdrop').hidden, false);
  assert.equal(document.querySelector('[name="employment_income"]').value, '100000.00');
  assert.equal(document.querySelector('[name="province_of_employment"]').value, 'QC');
  assert.match(document.querySelector('#income-message').textContent, /loaded for review/);
  assert.match(document.querySelector('#income-message').textContent, /PDF taxpayer: Alex/);
  assert.equal(calls.some(({url}) => url.startsWith('/api/income/people/')), false);

  const bonus = document.querySelector('[name="bonus"]');
  bonus.value = '10000';
  bonus.dispatchEvent(new dom.window.Event('input', {bubbles: true}));
  assert.match(document.querySelector('#income-salary-rate').textContent, /90,000/);

  document.querySelector('#income-form').dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
  await tick(); await tick();
  assert.equal(calls.some(({url, options}) => url === '/api/income/people/1/years/2024' && options.method === 'PUT'), true);
  assert.equal(document.querySelector('#income-dialog-backdrop').hidden, true);

  document.querySelector('[data-person-id="2"]').click();
  await tick();
  assert.ok(calls.some(({url}) => url === '/api/income?person_id=2'));
  dom.window.close();
});

test('income screen rejects a document for another person', async () => {
  const dom = installDom();
  globalThis.fetch = async (url) => {
    if (url === '/api/model/people') return {ok: true, json: async () => ({people: [{id: 1, name: 'Alex'}]})};
    if (String(url).startsWith('/api/income?')) return {ok: true, json: async () => ({records: []})};
    if (url === '/api/income/import/preview') {
      return {ok: true, json: async () => ({...annualRecord(), taxpayer_name: 'Jordan'})};
    }
    throw new Error(`Unexpected URL ${url}`);
  };
  await import(`../../static/income.mjs?mismatch=${Date.now()}`);
  await tick(); await tick();
  document.querySelector('#income-import').click();
  document.querySelector('#ufile-form').dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
  await tick(); await tick();
  assert.match(document.querySelector('#income-message').textContent, /selected person is Alex/);
  assert.equal(document.querySelector('#income-dialog-backdrop').hidden, true);
  dom.window.close();
});

test('income screen handles missing people and request errors', async () => {
  const dom = installDom();
  globalThis.fetch = async (url) => {
    if (url === '/api/model/people') return {ok: true, json: async () => ({people: []})};
    return {ok: false, json: async () => ({error: 'Broken import'})};
  };

  await import(`../../static/income.mjs?empty=${Date.now()}`);
  await tick(); await tick();
  assert.match(document.querySelector('#income-message').textContent, /Add a person/);
  assert.equal(document.querySelector('#income-add').disabled, true);
  assert.match(document.querySelector('#income-history').textContent, /No annual employment/);

  document.querySelector('#ufile-form').dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
  await tick();
  assert.match(document.querySelector('#income-message').textContent, /Broken import/);
  assert.equal(document.querySelector('#income-message').classList.contains('error'), true);
  dom.window.close();
});
