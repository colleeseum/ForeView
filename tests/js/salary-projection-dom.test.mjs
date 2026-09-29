import assert from 'node:assert/strict';
import test from 'node:test';

import {JSDOM} from 'jsdom';

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

function projection(year, salary = '100000.00') {
  return {
    year, age: 46, annual_salary_rate: salary, raise_rate: year === 2026 ? null : '0.04',
    gross_income: salary, rrsp_contribution: '10000.00', rrsp_deduction: '10000.00',
    other_income: '0.00', cpp_qpp: '4646.45', ei: '1123.07', qpip: '442.90',
    federal_tax: '12000.00', quebec_tax: '14000.00', net_income_after_tax: '67887.58',
    disposable_income: '57887.58', rule_year: 2026, rules_held_constant: year > 2026,
  };
}

function model() {
  return {
    scenarios: [{id: 3, name: 'Baseline'}], selected_scenario_id: 3,
    start_year: 2026, end_year: 2027,
    people: [{
      id: 2, name: 'Alex', birth_date: '1980-04-15', error: null,
      baseline: {annual_salary: '100000.00', effective_date: '2026-01-01', province_of_employment: 'ON', payroll_plan: 'CPP'},
      settings: {default_raise: '0.04', retirement_date: null, recurring_rrsp_contribution: '10000.00', recurring_rrsp_deduction: '10000.00', recurring_other_income: '0.00'},
      salary_anchor: {
        year: 2025, annual_salary_rate: '95000.00', province_of_employment: 'ON', payroll_plan: 'CPP',
        rrsp_contribution: '10000.00', rrsp_deduction: '9000.00', other_income: '1500.00',
      },
      overrides: [], actuals: [], projection: [projection(2026), projection(2027, '104000.00')],
    }],
    household: [{...projection(2026)}, {...projection(2027, '104000.00')}],
  };
}

test('salary projection loads, edits assumptions and annual overrides, and shows household', async () => {
  const dom = new JSDOM(`<!doctype html><body>
    <select id="salary-scenario"></select><input id="salary-start-year"><input id="salary-end-year"><button id="salary-view"></button>
    <p id="salary-message"></p><nav id="salary-tabs"></nav><section id="salary-setup" hidden><p id="salary-source-note"></p>
      <output id="salary-current-rate"></output><output id="salary-current-year"></output>
      <output id="salary-current-province"></output><output id="salary-current-payroll"></output>
      <output id="salary-current-rrsp-contribution"></output><output id="salary-current-rrsp-deduction"></output>
      <output id="salary-current-other-income"></output>
    </section>
    <form id="salary-settings-form">
      <input name="default_raise"><input name="retirement_date">
      <button id="salary-save" type="submit" disabled></button>
    </form><span id="salary-annual-status"></span>
    <button id="salary-annual-discard" disabled></button><button id="salary-annual-save" disabled></button>
    <div id="salary-table"></div></body>`, {url: 'http://localhost/salary-projection'});
  globalThis.window = dom.window;
  globalThis.document = dom.window.document;
  globalThis.FormData = dom.window.FormData;
  globalThis.URLSearchParams = dom.window.URLSearchParams;
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({url: String(url), options});
    return {ok: true, json: async () => String(url).startsWith('/api/salary-projection?') ? model() : {saved: true}};
  };

  const module = await import(`../../static/salary-projection.mjs?test=${Date.now()}`);
  await tick();
  assert.match(document.querySelector('#salary-table').innerHTML, /100,000/);
  assert.equal(document.querySelector('[name="default_raise"]').value, '4');
  assert.match(document.querySelector('#salary-source-note').textContent, /2025/);
  assert.match(document.querySelector('#salary-current-rate').textContent, /95,000/);
  assert.equal(document.querySelector('#salary-current-province').textContent, 'ON');
  assert.equal(document.querySelector('#salary-current-payroll').textContent, 'CPP');
  assert.match(document.querySelector('#salary-current-rrsp-contribution').textContent, /10,000/);
  assert.match(document.querySelector('#salary-current-rrsp-deduction').textContent, /9,000/);
  assert.match(document.querySelector('#salary-current-other-income').textContent, /1,500/);
  assert.equal(document.querySelector('#salary-save').disabled, true);
  assert.equal(module.money('12.50'), '$13');
  assert.match(module.projectionTable([]), /No projection/);

  document.querySelector('[data-person-key="household"]').click();
  assert.match(document.querySelector('#salary-message').textContent, /sum of individual/);
  assert.equal(document.querySelector('#salary-setup').hidden, true);
  document.querySelector('[data-person-key="2"]').click();

  document.querySelector('[name="default_raise"]').value = '4.5';
  document.querySelector('[name="default_raise"]').dispatchEvent(new dom.window.Event('input', {bubbles: true}));
  assert.equal(document.querySelector('#salary-save').disabled, false);
  document.querySelector('#salary-settings-form').dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
  await tick(); await tick();
  assert.equal(document.querySelector('#salary-save').disabled, true);
  assert.equal(calls.some((item) => item.url.endsWith('/baseline')), false);
  assert.ok(calls.some((item) => item.url.endsWith('/settings') && item.options.method === 'PUT'));
  const settingsCall = calls.find((item) => item.url.endsWith('/settings') && item.options.method === 'PUT');
  assert.deepEqual(Object.keys(JSON.parse(settingsCall.options.body)).sort(), ['default_raise', 'retirement_date']);

  const salaryInput = document.querySelector('.salary-year-input[data-year="2027"][data-field="salary"]');
  salaryInput.value = '120000';
  salaryInput.dispatchEvent(new dom.window.Event('input', {bubbles: true}));
  assert.equal(document.querySelector('#salary-annual-save').disabled, false);
  assert.match(document.querySelector('#salary-annual-status').textContent, /1 unsaved/);
  assert.equal(calls.some((item) => item.url.endsWith('/overrides')), false);
  document.querySelector('#salary-annual-save').click();
  await tick(); await tick();
  const override = calls.find((item) => item.url.endsWith('/overrides'));
  assert.equal(override.options.method, 'PUT');
  assert.equal(JSON.parse(override.options.body).overrides[0].salary, '120000');
  assert.equal(document.querySelector('#salary-annual-save').disabled, true);

  document.querySelector('#salary-view').click();
  await tick();
  assert.ok(calls.filter((item) => item.url.startsWith('/api/salary-projection?')).length >= 4);
});

test('salary projection helpers render actual and manual override states', async () => {
  const module = await import('../../static/salary-projection.mjs');
  const actual = {...projection(2025), actual: true, source: 'Assessment'};
  const html = module.projectionTable([actual, projection(2026)], {
    editable: true,
    overrides: [{year: 2026, salary: '100000.00'}],
  });
  assert.match(html, /2025 Actual/);
  assert.match(html, /Assessment/);
  assert.match(html, /manual-override/);
  assert.match(module.projectionTable([{...actual, source: null}]), /Recorded/);
  assert.match(module.projectionTable([{...projection(2026), annual_salary_rate: 0, raise_rate: 0}], {editable: true}), /value="0.00"/);
  assert.equal(module.householdRows([{year: 2026}])[0].age, null);
});

test('salary projection explains missing scenarios without mutating data', async () => {
  const dom = new JSDOM(`<!doctype html><body>
    <select id="salary-scenario"></select><input id="salary-start-year"><input id="salary-end-year"><button id="salary-view"></button>
    <p id="salary-message"></p><nav id="salary-tabs"></nav><section id="salary-setup"></section>
    <form id="salary-settings-form"></form><div id="salary-table"></div></body>`, {url: 'http://localhost/salary-projection'});
  globalThis.window = dom.window;
  globalThis.document = dom.window.document;
  globalThis.URLSearchParams = dom.window.URLSearchParams;
  globalThis.fetch = async () => ({ok: true, json: async () => ({scenarios: [], people: [], household: [], selected_scenario_id: null, start_year: 2026, end_year: 2035})});

  await import(`../../static/salary-projection.mjs?empty=${Date.now()}`);
  await tick();
  assert.match(document.querySelector('#salary-table').innerHTML, /Create a scenario/);
  assert.equal(document.querySelector('#salary-setup').hidden, true);
});

test('salary projection shows defaults and a per-person calculation error', async () => {
  const dom = new JSDOM(`<!doctype html><body>
    <select id="salary-scenario"></select><input id="salary-start-year"><input id="salary-end-year"><button id="salary-view"></button>
    <p id="salary-message"></p><nav id="salary-tabs"></nav><section id="salary-setup"></section>
    <form id="salary-settings-form"><input name="default_raise"><input name="retirement_date"><button id="salary-save" type="submit"></button></form>
    <div id="salary-table"></div></body>`, {url: 'http://localhost/salary-projection'});
  globalThis.window = dom.window;
  globalThis.document = dom.window.document;
  globalThis.FormData = dom.window.FormData;
  globalThis.URLSearchParams = dom.window.URLSearchParams;
  globalThis.fetch = async () => ({ok: true, json: async () => ({
    scenarios: [{id: 1, name: 'Test'}], selected_scenario_id: 1, start_year: 2026, end_year: 2026,
    people: [{id: 9, name: 'No income', baseline: null, settings: null, salary_anchor: null, overrides: [], actuals: [], projection: [], error: 'Add a factual Income record'}], household: [],
  })});

  await import(`../../static/salary-projection.mjs?defaults=${Date.now()}`);
  await tick();
  assert.equal(document.querySelector('[name="default_raise"]').value, '0');
  assert.match(document.querySelector('#salary-message').textContent, /factual Income record/);
  assert.equal(document.querySelector('#salary-message').classList.contains('error'), true);
  document.querySelector('#salary-tabs').click();
});
