import assert from 'node:assert/strict';
import test from 'node:test';

import {JSDOM} from 'jsdom';

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

function installDom() {
  const fields = [
    'employment_income', 'bonus', 'other_income', 'interest_income', 'cpp_qpp', 'ei', 'qpip',
    'rrsp_contribution', 'rrsp_deduction', 'federal_tax', 'provincial_tax',
  ].map((name) => `<input name="${name}" value="0">`).join('');
  const dom = new JSDOM(`<!doctype html><body>
    <div id="income-tabs"></div><div id="income-summary"></div><p id="income-message"></p>
    <div id="income-history"></div><div id="income-tax-returns"></div><div id="income-assessments"></div>
    <div id="income-rooms"></div><div id="income-pension"></div><div id="income-normalized"></div>
    <button id="income-add"></button><button id="income-import"></button>
    <div id="income-dialog-backdrop" hidden></div><button id="income-dialog-close"></button><p id="income-editor-person"></p>
    <form id="income-form"><input name="tax_year" value="2025"><select name="province_of_residence"><option value=""></option><option value="ON">ON</option><option value="QC">QC</option></select><input name="payroll_plan">${fields}<select name="source"><option>T1</option><option>UFile T1</option><option>Manual</option></select><button type="submit"></button></form>
    <output id="income-salary-rate"></output>
    <div id="income-correction-backdrop" hidden><button id="income-correction-close"></button>
      <h2 id="income-correction-title"></h2><p id="income-correction-context"></p>
      <div id="income-correction-status" hidden></div>
      <strong id="income-correction-source-amount"></strong><small id="income-correction-source-note"></small>
      <strong id="income-correction-current-amount"></strong><small id="income-correction-current-note"></small>
      <form id="income-correction-form"><input name="correct_amount"><textarea name="reason"></textarea>
        <button id="income-correction-remove" type="button" hidden></button>
        <button id="income-correction-confirm" type="button" hidden></button>
        <button id="income-correction-save" type="submit" disabled></button>
      </form>
      <p id="income-correction-message"></p><details id="income-correction-history-panel"><div id="income-correction-history"></div></details>
    </div>
    <div id="ufile-dialog-backdrop" hidden></div><button id="ufile-dialog-close"></button>
    <form id="ufile-form"><input id="income-import-file" name="file" type="file"><div id="income-import-progress" hidden></div><div id="income-import-review" hidden></div><button id="income-import-preview" type="submit" disabled></button><button id="income-import-confirm" type="button" hidden></button></form>
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
    province_of_residence: 'ON', payroll_plan: 'CPP',
    bonus: '5000.00', salary_rate: '95000.00', other_income: '1000.00',
    interest_income: '250.00', tax_values: [],
    gross_income: '101000.00', cpp_qpp: '4000.00', ei: '900.00', qpip: '400.00',
    rrsp_contribution: '10000.00', rrsp_deduction: '10000.00',
    federal_tax: '12000.00', provincial_tax: '13000.00',
    disposable_income: '60700.00', source: 'UFile T1', ...overrides,
  };
}

function latestSnapshot() {
  return {
    tax_year: 2025, available_years: [2025, 2024], values: [
      {concept: 'employment_income', label: 'Employment income', amount: '101500.00', source: 'Revenu Québec notice', document_kind: 'assessment', jurisdiction: 'CA-QC', line_code: '101'},
      {concept: 'interest_investment_income', label: 'Interest and investment income', amount: '250.00', source: 'UFile T1', document_kind: 'return', jurisdiction: 'CA', line_code: '12100'},
      {concept: 'oas_income', label: 'OAS income', amount: '0.00', source: 'UFile T1', document_kind: 'return', jurisdiction: 'CA', line_code: '11300'},
    ],
  };
}

function factualCorrection(overrides = {}) {
  return {
    id: 21, person_id: 1, tax_year: 2025, concept: 'employment_income',
    label: 'Employment income', revision_number: 2, revision_kind: 'edit',
    correct_amount: '103000.00', reason: 'Supporting payroll records differ.',
    created_at: '2026-10-03 12:00:00', review_required: false,
    source_at_correction: {
      amount: '101500.00', document_kind: 'return', jurisdiction: 'CA',
      line_code: '10100', source: 'UFile T1', source_version: '2026.09.29',
      document_hash: 'original-hash',
    },
    current_underlying: {
      amount: '101500.00', document_kind: 'return', jurisdiction: 'CA',
      line_code: '10100', source: 'UFile T1', source_version: '2026.09.29',
      document_hash: 'original-hash',
    },
    ...overrides,
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
      return {ok: true, json: async () => ({
        records: saved ? [annualRecord()] : [annualRecord(), annualRecord({id: 3, year: 2024, employment_income: '90000.00'})],
        tax_values: [{
          tax_year: 2025, document_kind: 'return', jurisdiction: 'CA', effective_year: 2025,
          line_code: '12100', description: 'Interest and investment income',
          reported_amount: '250.00', determined_amount: null, source: 'Another Tax App',
        }],
        snapshot: latestSnapshot(),
      })};
    }
    if (url === '/api/income/import/preview') {
      return {ok: true, json: async () => annualRecord({kind: 'tax_return', year: 2024, province_of_residence: 'QC', taxpayer_name: 'Alex', source_name: 'UFile T1 PDF', source_version: '2026.09.29.1', document_hash: 'abc', tax_values: [{concept: 'interest_investment_income', description: 'Interest and other investment income', reported_amount: '250.00', determined_amount: null, line_code: '12100', effective_year: 2024}]})};
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
  assert.match(document.querySelector('#income-history').textContent, /Edit/);
  assert.match(document.querySelector('#income-tax-returns').textContent, /Another Tax App/);
  assert.match(document.querySelector('#income-summary').textContent, /Tax year 2025/);
  assert.match(document.querySelector('#income-summary').textContent, /Revenu Québec notice · assessed · CA-QC · line 101/);
  assert.doesNotMatch(document.querySelector('#income-summary').textContent, /OAS income/);
  assert.equal(document.querySelector('#income-dialog-backdrop').hidden, true);
  assert.equal(document.body.innerHTML.includes('<b>Jordan</b>'), false);

  document.querySelector('[data-edit-year="2024"]').click();
  assert.equal(document.querySelector('#income-dialog-backdrop').hidden, false);
  assert.equal(document.querySelector('[name="tax_year"]').value, '2024');
  assert.equal(document.querySelector('[name="tax_year"]').disabled, true);
  assert.equal(document.querySelector('[name="province_of_residence"]').value, 'ON');
  document.querySelector('#income-dialog-close').click();
  assert.equal(document.querySelector('#income-dialog-backdrop').hidden, true);
  document.querySelector('#income-add').click();
  assert.equal(document.querySelector('[name="tax_year"]').disabled, false);
  document.querySelector('#income-dialog-close').click();

  document.querySelector('#income-import').click();
  assert.equal(document.querySelector('#ufile-dialog-backdrop').hidden, false);
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
  assert.equal(document.querySelector('#income-import-progress').hidden, false);
  await tick(); await tick();
  assert.equal(document.querySelector('#income-import-progress').hidden, true);
  assert.equal(document.querySelector('[name="tax_year"]').value, '2024');
  assert.equal(document.querySelector('#income-dialog-backdrop').hidden, false);
  assert.equal(document.querySelector('[name="employment_income"]').value, '100000.00');
  assert.equal(document.querySelector('[name="province_of_residence"]').value, 'QC');
  assert.equal(document.querySelector('[name="interest_income"]').value, '250.00');
  assert.equal(document.querySelector('#income-editor-person').textContent, 'Person: Alex');
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
  const savedCall = calls.find(({url}) => url === '/api/income/people/1/years/2024');
  assert.equal(JSON.parse(savedCall.options.body).tax_values[0].concept, 'interest_investment_income');
  assert.equal(document.querySelector('#income-dialog-backdrop').hidden, true);

  document.querySelector('[data-person-id="2"]').click();
  await tick();
  assert.ok(calls.some(({url}) => url === '/api/income?person_id=2'));
  dom.window.close();
});

test('income screen creates a correction and can select a historical snapshot', async () => {
  const dom = installDom();
  const calls = [];
  let created = false;
  globalThis.fetch = async (url, options = {}) => {
    const address = String(url);
    calls.push({url: address, options});
    if (address === '/api/model/people') {
      return {ok: true, json: async () => ({people: [{id: 1, name: 'Alex'}]})};
    }
    if (address.includes('/api/income/corrections/person/1/year/')) {
      return {ok: true, json: async () => ({corrections: []})};
    }
    if (address === '/api/income/corrections' && options.method === 'POST') {
      created = true;
      return {ok: true, json: async () => factualCorrection({revision_number: 1, revision_kind: 'create', correct_amount: '102000.00'})};
    }
    if (address === '/api/income?person_id=1&year=2024') {
      return {ok: true, json: async () => ({
        records: [], assessments: [], registered_rooms: [], tax_values: [], corrections: [],
        snapshot: {
          tax_year: 2024, available_years: [2025, 2024], values: [
            {concept: 'employment_income', label: 'Employment income', amount: '90000.00', source: 'UFile T1', document_kind: 'return', jurisdiction: 'CA', line_code: '10100'},
          ],
        },
      })};
    }
    if (address === '/api/income?person_id=1') {
      const snapshot = latestSnapshot();
      if (created) {
        snapshot.values[0] = {...snapshot.values[0], amount: '102000.00', source: 'Corrected value', document_kind: 'correction'};
      }
      return {ok: true, json: async () => ({
        records: [annualRecord()], assessments: [], registered_rooms: [], tax_values: [],
        snapshot, corrections: created ? [factualCorrection({revision_number: 1, revision_kind: 'create', correct_amount: '102000.00'})] : [],
      })};
    }
    throw new Error(`Unexpected URL ${address}`);
  };

  await import(`../../static/income.mjs?correction-create=${Date.now()}`);
  await tick(); await tick();
  document.querySelector('[data-correct-concept="employment_income"]').click();
  await tick();
  assert.equal(document.querySelector('#income-correction-backdrop').hidden, false);
  assert.equal(document.querySelector('#income-correction-source-amount').textContent, '$101,500.00');
  assert.equal(document.querySelector('#income-correction-save').disabled, true);

  const amount = document.querySelector('#income-correction-form [name="correct_amount"]');
  const reason = document.querySelector('#income-correction-form [name="reason"]');
  amount.value = '102000';
  reason.value = 'Payroll records include the corrected amount.';
  reason.dispatchEvent(new dom.window.Event('input', {bubbles: true}));
  assert.equal(document.querySelector('#income-correction-save').disabled, false);
  document.querySelector('#income-correction-form').dispatchEvent(
    new dom.window.Event('submit', {bubbles: true, cancelable: true}),
  );
  await tick(); await tick();
  const createCall = calls.find(({url, options}) => url === '/api/income/corrections' && options.method === 'POST');
  assert.deepEqual(JSON.parse(createCall.options.body), {
    person_id: 1, tax_year: 2025, concept: 'employment_income',
    correct_amount: '102000', reason: 'Payroll records include the corrected amount.',
    expected_revision: 0,
  });
  assert.match(document.querySelector('#income-summary').textContent, /Corrected/);
  assert.match(document.querySelector('#income-message').textContent, /correction saved/);

  const yearFilter = document.querySelector('[data-income-snapshot-year]');
  yearFilter.value = '2024';
  yearFilter.dispatchEvent(new dom.window.Event('change', {bubbles: true}));
  await tick(); await tick();
  assert.ok(calls.some(({url}) => url === '/api/income?person_id=1&year=2024'));
  assert.match(document.querySelector('#income-summary').textContent, /Historical consolidated snapshot/);
  assert.match(document.querySelector('#income-summary').textContent, /90,000/);
  dom.window.close();
});

test('income screen reviews, edits, confirms, and removes a correction', async () => {
  const dom = installDom();
  const calls = [];
  let mode = 'review';
  let revision = 2;
  function activeCorrection() {
    if (mode === 'removed') return [];
    return [factualCorrection({
      revision_number: revision,
      review_required: mode === 'review',
      current_underlying: {
        amount: '102000.00', document_kind: 'return', jurisdiction: 'CA',
        line_code: '10100', source: 'UFile T1 updated', source_version: '2026.10.03',
        document_hash: 'updated-hash',
      },
    })];
  }
  globalThis.fetch = async (url, options = {}) => {
    const address = String(url);
    calls.push({url: address, options});
    if (address === '/api/model/people') {
      return {ok: true, json: async () => ({people: [{id: 1, name: 'Alex'}]})};
    }
    if (address === '/api/income?person_id=1') {
      const snapshot = latestSnapshot();
      snapshot.values[0] = mode === 'removed'
        ? {...snapshot.values[0], amount: '102000.00', source: 'UFile T1 updated', document_kind: 'return'}
        : {...snapshot.values[0], amount: '103000.00', source: 'Corrected value', document_kind: 'correction'};
      return {ok: true, json: async () => ({
        records: [annualRecord()], assessments: [], registered_rooms: [], tax_values: [],
        snapshot, corrections: activeCorrection(),
      })};
    }
    if (address.includes('/api/income/corrections/person/1/year/2025/')) {
      const current = factualCorrection({
        revision_number: revision,
        revision_kind: mode === 'removed' ? 'remove' : 'edit',
        review_required: mode === 'review',
      });
      return {ok: true, json: async () => ({
        corrections: [factualCorrection({id: 20, revision_number: 1, revision_kind: 'create'}), current],
      })};
    }
    if (address.endsWith('/confirm') && options.method === 'POST') {
      mode = 'confirmed'; revision = 3;
      return {ok: true, json: async () => factualCorrection({revision_number: revision, revision_kind: 'confirm'})};
    }
    if (address === '/api/income/corrections/21' && options.method === 'PUT') {
      mode = 'edited'; revision = 4;
      return {ok: true, json: async () => factualCorrection({revision_number: revision, revision_kind: 'edit'})};
    }
    if (address === '/api/income/corrections/21' && options.method === 'DELETE') {
      mode = 'removed'; revision = 5;
      return {ok: true, json: async () => factualCorrection({revision_number: revision, revision_kind: 'remove'})};
    }
    if (address === '/api/income/corrections' && options.method === 'POST') {
      mode = 'reactivated'; revision = 6;
      return {ok: true, json: async () => factualCorrection({revision_number: revision, revision_kind: 'create'})};
    }
    throw new Error(`Unexpected URL ${address}`);
  };

  await import(`../../static/income.mjs?correction-lifecycle=${Date.now()}`);
  await tick(); await tick();
  assert.match(document.querySelector('#income-summary').textContent, /Review required/);
  document.querySelector('[data-correct-concept="employment_income"]').click();
  await tick(); await tick();
  assert.match(document.querySelector('#income-correction-status').textContent, /underlying value or provenance has changed/);
  assert.equal(document.querySelector('#income-correction-source-amount').textContent, '$101,500.00');
  assert.equal(document.querySelector('#income-correction-current-amount').textContent, '$102,000.00');
  assert.match(document.querySelector('#income-correction-history').textContent, /Revision 2/);
  assert.equal(document.querySelector('#income-correction-confirm').hidden, false);

  document.querySelector('#income-correction-confirm').click();
  await tick(); await tick();
  const confirmCall = calls.find(({url}) => url.endsWith('/confirm'));
  assert.equal(JSON.parse(confirmCall.options.body).expected_revision, 2);
  assert.doesNotMatch(document.querySelector('#income-summary').textContent, /Review required/);

  document.querySelector('[data-correct-concept="employment_income"]').click();
  await tick();
  const reason = document.querySelector('#income-correction-form [name="reason"]');
  reason.value = 'Updated supporting records.';
  reason.dispatchEvent(new dom.window.Event('input', {bubbles: true}));
  document.querySelector('#income-correction-form').dispatchEvent(
    new dom.window.Event('submit', {bubbles: true, cancelable: true}),
  );
  await tick(); await tick();
  const editCall = calls.find(({url, options}) => url === '/api/income/corrections/21' && options.method === 'PUT');
  assert.equal(JSON.parse(editCall.options.body).expected_revision, 3);

  document.querySelector('[data-correct-concept="employment_income"]').click();
  await tick();
  document.querySelector('#income-correction-remove').click();
  await tick(); await tick();
  const removeCall = calls.find(({url, options}) => url === '/api/income/corrections/21' && options.method === 'DELETE');
  assert.equal(JSON.parse(removeCall.options.body).expected_revision, 4);
  assert.doesNotMatch(document.querySelector('#income-summary').textContent, /Corrected/);
  assert.match(document.querySelector('#income-message').textContent, /Source precedence restored/);

  document.querySelector('[data-correct-concept="employment_income"]').click();
  await tick();
  const reactivatedAmount = document.querySelector('#income-correction-form [name="correct_amount"]');
  const reactivatedReason = document.querySelector('#income-correction-form [name="reason"]');
  reactivatedAmount.value = '104000';
  reactivatedReason.value = 'New supporting evidence.';
  reactivatedReason.dispatchEvent(new dom.window.Event('input', {bubbles: true}));
  document.querySelector('#income-correction-form').dispatchEvent(
    new dom.window.Event('submit', {bubbles: true, cancelable: true}),
  );
  await tick(); await tick();
  const reactivateCall = calls.filter(
    ({url, options}) => url === '/api/income/corrections' && options.method === 'POST',
  ).at(-1);
  assert.equal(JSON.parse(reactivateCall.options.body).expected_revision, 5);
  assert.match(document.querySelector('#income-summary').textContent, /Corrected/);
  dom.window.close();
});

test('income screen rejects a document for a person who is not configured', async () => {
  const dom = installDom();
  globalThis.fetch = async (url) => {
    if (url === '/api/model/people') return {ok: true, json: async () => ({people: [{id: 1, name: 'Alex'}]})};
    if (String(url).startsWith('/api/income?')) return {ok: true, json: async () => ({records: []})};
    if (url === '/api/income/import/preview') {
      return {ok: true, json: async () => ({...annualRecord(), kind: 'tax_return', taxpayer_name: 'Jordan'})};
    }
    throw new Error(`Unexpected URL ${url}`);
  };
  await import(`../../static/income.mjs?mismatch=${Date.now()}`);
  await tick(); await tick();
  document.querySelector('#income-import').click();
  document.querySelector('#ufile-form').dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
  await tick(); await tick();
  assert.match(document.querySelector('#income-message').textContent, /not configured/);
  assert.equal(document.querySelector('#income-dialog-backdrop').hidden, true);
  dom.window.close();
});

test('income screen selects the person identified by the PDF', async () => {
  const dom = installDom();
  globalThis.fetch = async (url) => {
    if (url === '/api/model/people') {
      return {ok: true, json: async () => ({people: [{id: 1, name: 'Alex'}, {id: 2, name: 'Jordan'}]})};
    }
    if (String(url).startsWith('/api/income?')) {
      return {ok: true, json: async () => ({records: []})};
    }
    if (url === '/api/income/import/preview') {
      return {ok: true, json: async () => ({...annualRecord(), kind: 'tax_return', taxpayer_name: 'Jordan'})};
    }
    throw new Error(`Unexpected URL ${url}`);
  };
  await import(`../../static/income.mjs?identified=${Date.now()}`);
  await tick(); await tick();
  document.querySelector('#income-import').click();
  document.querySelector('#ufile-form').dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
  await tick(); await tick();
  assert.equal(document.querySelector('#income-editor-person').textContent, 'Person: Jordan');
  assert.equal(document.querySelector('[data-person-id="2"]').classList.contains('active'), true);
  dom.window.close();
});

test('income screen reviews and saves an assessment with registered room', async () => {
  const dom = installDom();
  const calls = [];
  const assessment = {
    kind: 'tax_assessment', tax_year: 2025, jurisdiction: 'CA', issued_on: '2026-05-11',
    taxpayer_name: 'Alex', total_income: '223074.00', net_income: '214510.00',
    taxable_income: '214510.00', net_tax: '43995.95', additional_contributions: '0.00',
    tax_withheld: '47010.24', balance: '-10273.62', rrsp_effective_year: 2026,
    rrsp_deduction_limit: '58810.00', rrsp_unused_deduction_room: '25000.00',
    rrsp_new_room: '33810.00', rrsp_unused_contributions: '0.00',
    rrsp_available_room: '58810.00', source: 'CRA NOA', source_name: 'CRA notice',
    source_version: '2026.09.29', document_hash: 'abc',
  };
  globalThis.fetch = async (url, options = {}) => {
    calls.push({url: String(url), options});
    if (url === '/api/model/people') return {ok: true, json: async () => ({people: [{id: 1, name: 'Alex'}]})};
    if (String(url).startsWith('/api/income?')) return {ok: true, json: async () => ({
      records: [annualRecord()], assessments: [assessment], tax_values: [{tax_year: 2025, document_kind: 'assessment', jurisdiction: 'CA', effective_year: 2026, line_code: null, description: 'Canada training credit limit', reported_amount: null, determined_amount: '250.00', source: 'CRA NOA'}],
      registered_rooms: [
        {plan_type: 'RRSP', effective_year: 2026, available_room: '58810.00', deduction_limit: '58810.00', unused_contributions: '0.00', as_of_date: '2026-05-11', source: 'CRA NOA'},
        {plan_type: 'RRSP', effective_year: 2025, available_room: '50000.00', deduction_limit: '50000.00', unused_contributions: '0.00', as_of_date: '2025-05-11', source: 'CRA NOA'},
      ],
      public_pension: {provider: 'QPP', issued_on: '2026-06-15', excludes_second_enhancement: true, estimates: [{contribution_assumption: 'stop', activation_age: 65, monthly_amount: '1012.00'}], earnings: [{year: 2025, qpp_earnings: '0.00', cpp_earnings: '81200.00', status: 'A'}]},
      snapshot: latestSnapshot(),
    })};
    if (url === '/api/income/import/preview') return {ok: true, json: async () => assessment};
    if (url === '/api/income/people/1/assessments') return {ok: true, json: async () => assessment};
    throw new Error(`Unexpected URL ${url}`);
  };

  await import(`../../static/income.mjs?assessment=${Date.now()}`);
  await tick(); await tick();
  assert.match(document.querySelector('#income-rooms').textContent, /58,810/);
  assert.match(document.querySelector('#income-pension').textContent, /1,012/);
  assert.match(document.querySelector('#income-summary').textContent, /RRSP available room/);
  assert.match(document.querySelector('#income-summary').textContent, /58,810/);
  assert.doesNotMatch(document.querySelector('#income-summary').textContent, /50,000/);
  document.querySelector('#income-import').click();
  document.querySelector('#ufile-form').dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
  await tick(); await tick();
  assert.match(document.querySelector('#income-import-review').textContent, /RRSP room/);
  assert.equal(document.querySelector('#income-import-preview').hidden, true);
  document.querySelector('#income-import-confirm').click();
  await tick(); await tick();
  assert.ok(calls.some(({url, options}) => url === '/api/income/people/1/assessments' && options.method === 'POST'));
  dom.window.close();
});

test('income screen reviews and saves a public pension statement', async () => {
  const dom = installDom();
  const calls = [];
  const statement = {
    kind: 'public_pension_statement', issued_on: '2026-06-15', taxpayer_name: '',
    provider: 'QPP', excludes_second_enhancement: false,
    earnings: [{year: 2025, qpp_earnings: '0.00', cpp_earnings: '81200.00', status: 'A'}],
    estimates: [{contribution_assumption: 'continue', activation_age: 65, monthly_amount: '1435.00'}],
    source_name: 'Retraite Quebec statement', source_version: '2026.09.29', document_hash: 'def',
  };
  globalThis.fetch = async (url, options = {}) => {
    calls.push({url: String(url), options});
    if (url === '/api/model/people') return {ok: true, json: async () => ({people: [{id: 1, name: 'Alex'}]})};
    if (String(url).startsWith('/api/income?')) return {ok: true, json: async () => ({records: [], assessments: [], registered_rooms: [], public_pension: null})};
    if (url === '/api/income/import/preview') return {ok: true, json: async () => statement};
    if (url === '/api/income/people/1/public-pension-statements') return {ok: true, json: async () => ({id: 1})};
    throw new Error(`Unexpected URL ${url}`);
  };

  await import(`../../static/income.mjs?pension=${Date.now()}`);
  await tick(); await tick();
  document.querySelector('#income-import').click();
  document.querySelector('#ufile-form').dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
  await tick(); await tick();
  assert.match(document.querySelector('#income-import-review').textContent, /1 years/);
  document.querySelector('#income-import-confirm').click();
  await tick(); await tick();
  assert.ok(calls.some(({url, options}) => url === '/api/income/people/1/public-pension-statements' && options.method === 'POST'));
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
  assert.match(document.querySelector('#income-history').textContent, /No filed return or manual annual record/);

  document.querySelector('#ufile-form').dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
  await tick();
  assert.match(document.querySelector('#income-message').textContent, /Broken import/);
  assert.equal(document.querySelector('#income-message').classList.contains('error'), true);
  dom.window.close();
});
