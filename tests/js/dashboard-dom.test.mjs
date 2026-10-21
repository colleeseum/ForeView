// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import test from 'node:test';
import {readFileSync} from 'node:fs';
import {JSDOM} from 'jsdom';
import {configureLocalization} from '../../static/shared/i18n.mjs';
import {configureTestLocalization} from './localization-fixture.mjs';

test('synthetic RTL dashboard uses registered fallback and preserves source evidence', async () => {
  const catalogs = Object.fromEntries(['en-CA', 'fr-CA'].map((code) => [code,
    JSON.parse(readFileSync(new URL(`../../localization/${code}/browser.json`, import.meta.url))),
  ]));
  catalogs['ar-XB'] = {dashboard: {gross: 'RTL gross assets'}};
  configureLocalization({locale: 'ar-XB', fallbacks: ['fr-CA', 'en-CA'], catalogs});
  const styles = readFileSync(new URL('../../static/style.css', import.meta.url), 'utf8');
  const dom = new JSDOM(`<!doctype html><html lang="ar-XB" dir="rtl"><head><style>${styles}</style></head><body>
    <div id="dashboard-metrics"></div><div id="dashboard-categories"></div>
    <div id="dashboard-liquidity"></div><div id="dashboard-maturities"></div>
    <div id="dashboard-transactions"></div><button class="dialog-close"></button>
    <button class="full-help-button"></button><div class="help-drawer"></div>
  </body></html>`, {url: 'http://localhost/'});
  Object.assign(globalThis, {window: dom.window, document: dom.window.document});
  const data = {
    gross_assets: 1234.56, immovable_value: 0, invested_value: 0, gic_value: 0,
    liquidity_value: 0, liquidity_by_type: {non_registered: 0}, rrsp_uninvested: 0,
    uninvested_security_value: 0, savings_threshold: 0.025, low_rate_value: 0,
    categories: [], maturities: [],
    recent_transactions: [{transaction_date: '2026-01-01', institution: 'Synthetic Bank',
      account_number: '123', description: 'Original English statement', description_language: 'en-CA', amount: 5}],
  };
  const original = JSON.stringify(data);
  globalThis.fetch = async () => ({ok: true, json: async () => data});
  try {
    await import('../../static/dashboard/dashboard.mjs?synthetic-rtl');
    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.equal(document.documentElement.dir, 'rtl');
    assert.match(document.querySelector('#dashboard-metrics').textContent, /RTL gross assets/);
    assert.match(document.querySelector('#dashboard-maturities').textContent, /Aucune date d’échéance/);
    const source = document.querySelector('#dashboard-transactions td:nth-child(3) span');
    assert.equal(source.textContent, 'Original English statement');
    assert.equal(source.lang, 'en-CA');
    assert.equal(JSON.stringify(data), original);
    assert.doesNotMatch(document.body.textContent, /⟦/);
    // jsdom cannot measure visual RTL placement, but does validate the direction-neutral rules.
    for (const selector of ['.dialog-close', '.full-help-button', '.help-drawer']) {
      const computed = dom.window.getComputedStyle(document.querySelector(selector));
      assert.notEqual(computed.getPropertyValue('inset-inline-end'), '', selector);
      assert.equal(computed.getPropertyValue('right'), '', selector);
    }
  } finally {
    configureTestLocalization();
    dom.window.close();
  }
});

test('dashboard renders escaped financial summaries', async () => {
  configureTestLocalization();
  const dom = new JSDOM(`<!doctype html><body>
    <div id="dashboard-metrics"></div><div id="dashboard-categories"></div>
    <div id="dashboard-liquidity"></div><div id="dashboard-maturities"></div>
    <div id="dashboard-transactions"></div>
  </body>`, {url: 'http://localhost/'});
  Object.assign(globalThis, {window: dom.window, document: dom.window.document});
  const attack = '<img src=x onerror=alert(1)>';
  globalThis.fetch = async () => ({
    ok: true,
    json: async () => ({
      gross_assets: 1000,
      immovable_value: 400,
      invested_value: 300,
      gic_value: 100,
      liquidity_value: 200,
      liquidity_by_type: {non_registered: 150, tfsa: 50, rrsp: 25},
      rrsp_uninvested: 25,
      uninvested_security_value: 20,
      savings_threshold: 0.025,
      low_rate_value: 10,
      categories: [{label: attack, count: 1, total: 1000}],
      maturities: [{institution: attack, name: 'GIC', maturity_date: '2027-01-01', amount: 100}],
      recent_transactions: [{transaction_date: '2026-01-01', institution: attack, account_number: '1', description: attack, amount: 5}],
    }),
  });

  await import('../../static/dashboard/dashboard.mjs');
  await new Promise((resolve) => setTimeout(resolve, 0));

  assert.match(document.querySelector('#dashboard-metrics').textContent, /Gross assets/);
  assert.match(document.querySelector('#dashboard-liquidity').textContent, /RRSP uninvested/);
  assert.equal(document.body.innerHTML.includes(attack), false);
  assert.match(document.body.innerHTML, /&lt;img/);
  assert.equal(
    document.querySelector('#dashboard-transactions td:nth-child(3) span').lang,
    '',
  );
  dom.window.close();
});

test('dashboard renders empty activity states', async () => {
  configureTestLocalization();
  const dom = new JSDOM(`<!doctype html><body>
    <div id="dashboard-metrics"></div><div id="dashboard-categories"></div>
    <div id="dashboard-liquidity"></div><div id="dashboard-maturities"></div>
    <div id="dashboard-transactions"></div>
  </body>`, {url: 'http://localhost/'});
  Object.assign(globalThis, {window: dom.window, document: dom.window.document});
  globalThis.fetch = async () => ({
    ok: true,
    json: async () => ({
      gross_assets: 0, immovable_value: 0, invested_value: 0, gic_value: 0,
      liquidity_value: 0, liquidity_by_type: {non_registered: 0}, rrsp_uninvested: 0,
      uninvested_security_value: 0, savings_threshold: 0.025, low_rate_value: 0,
      categories: [{label: 'Empty', count: 2, total: 0}], maturities: [], recent_transactions: [],
    }),
  });
  await import('../../static/dashboard/dashboard.mjs?empty');
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.match(document.querySelector('#dashboard-categories').textContent, /2 accounts/);
  assert.match(document.querySelector('#dashboard-maturities').textContent, /No maturity dates/);
  assert.match(document.querySelector('#dashboard-transactions').textContent, /No transactions/);
  dom.window.close();
});

test('dashboard preserves malformed legacy dates without aborting rendering', async () => {
  configureTestLocalization();
  const dom = new JSDOM(`<!doctype html><body>
    <div id="dashboard-metrics"></div><div id="dashboard-categories"></div>
    <div id="dashboard-liquidity"></div><div id="dashboard-maturities"></div>
    <div id="dashboard-transactions"></div>
  </body>`, {url: 'http://localhost/'});
  Object.assign(globalThis, {window: dom.window, document: dom.window.document});
  globalThis.fetch = async () => ({
    ok: true,
    json: async () => ({
      gross_assets: 100, immovable_value: 0, invested_value: 0, gic_value: 100,
      liquidity_value: 0, liquidity_by_type: {non_registered: 0}, rrsp_uninvested: 0,
      uninvested_security_value: 0, savings_threshold: 0.025, low_rate_value: 0,
      categories: [],
      maturities: [
        {institution: 'Legacy Bank', name: 'GIC', maturity_date: '0000-01-01', amount: 100},
        {institution: 'Legacy Bank', name: 'GIC', maturity_date: '2026-02-30', amount: 100},
      ],
      recent_transactions: [{transaction_date: 'not-a-date', institution: 'Legacy Bank', account_number: '1', description: 'Legacy row', amount: 5}],
    }),
  });

  await import(`../../static/dashboard/dashboard.mjs?legacy-date=${Date.now()}`);
  await new Promise((resolve) => setTimeout(resolve, 0));

  assert.match(document.querySelector('#dashboard-metrics').textContent, /Gross assets/);
  assert.match(document.querySelector('#dashboard-maturities').textContent, /0000-01-01/);
  assert.match(document.querySelector('#dashboard-maturities').textContent, /2026-02-30/);
  assert.match(document.querySelector('#dashboard-transactions').textContent, /not-a-date/);
  dom.window.close();
});

test('dashboard renders browser-generated content in French', async () => {
  configureTestLocalization('fr-CA');
  const dom = new JSDOM(`<!doctype html><body>
    <div id="dashboard-metrics"></div><div id="dashboard-categories"></div>
    <div id="dashboard-liquidity"></div><div id="dashboard-maturities"></div>
    <div id="dashboard-transactions"></div>
  </body>`, {url: 'http://localhost/'});
  Object.assign(globalThis, {window: dom.window, document: dom.window.document});
  globalThis.fetch = async () => ({
    ok: true,
    json: async () => ({
      gross_assets: 1234.56, immovable_value: 0, invested_value: 0, gic_value: 0,
      liquidity_value: 0, liquidity_by_type: {non_registered: 0, tfsa: 0, resp: 0}, rrsp_uninvested: 0,
      uninvested_security_value: 0, savings_threshold: 0.025, low_rate_value: 0,
      categories: [{type: 'tfsa', label: 'TFSA', count: 1, total: 0}], maturities: [], recent_transactions: [],
    }),
  });
  await import('../../static/dashboard/dashboard.mjs?french');
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.match(document.querySelector('#dashboard-metrics').textContent, /Actif brut/);
  assert.match(
    document.querySelector('#dashboard-metrics .summary-pill strong').textContent,
    /^1[\s\u00a0\u202f]?234,56[\s\u00a0\u202f]*\$$/,
  );
  assert.match(document.querySelector('#dashboard-categories').textContent, /CELI/);
  assert.match(document.querySelector('#dashboard-liquidity').textContent, /CELI/);
  assert.match(document.querySelector('#dashboard-liquidity').textContent, /REEE/);
  assert.match(document.querySelector('#dashboard-maturities').textContent, /Aucune date d’échéance/);
  configureTestLocalization();
  dom.window.close();
});

test('dashboard preserves raw API error language inside a localized failure', async () => {
  configureTestLocalization('fr-CA');
  const dom = new JSDOM(`<!doctype html><body>
    <div id="dashboard-metrics"></div><div id="dashboard-categories"></div>
    <div id="dashboard-liquidity"></div><div id="dashboard-maturities"></div>
    <div id="dashboard-transactions"></div>
  </body>`, {url: 'http://localhost/'});
  Object.assign(globalThis, {window: dom.window, document: dom.window.document});
  globalThis.fetch = async () => ({
    ok: false,
    status: 503,
    json: async () => ({error: 'Database unavailable'}),
  });

  await import(`../../static/dashboard/dashboard.mjs?failure=${Date.now()}`);
  await new Promise((resolve) => setTimeout(resolve, 0));
  const message = document.querySelector('#dashboard-metrics .form-message');
  assert.match(message.textContent, /Impossible de charger le tableau de bord/);
  assert.equal(message.querySelector('[lang="en-CA"]').textContent, 'Database unavailable');
  configureTestLocalization();
  dom.window.close();
});

test('dashboard rejects unsafe amounts before rendering any financial panels', async () => {
  const cases = [
    ['gross_assets', 90071992547409.02],
    ['gross_assets', -(2 ** 44)],
    ['gross_assets', Number.MAX_VALUE],
    ['gross_assets', Infinity],
    ['gross_assets', '123.45'],
    ['category', 90071992547409.02],
    ['maturity', 90071992547409.02],
    ['transaction', 90071992547409.02],
  ];
  for (const [index, [target, amount]] of cases.entries()) {
    configureTestLocalization(index % 2 ? 'fr-CA' : 'en-CA');
    const dom = new JSDOM(`<!doctype html><body>
      <div id="dashboard-metrics"></div><div id="dashboard-categories"></div>
      <div id="dashboard-liquidity"></div><div id="dashboard-maturities"></div>
      <div id="dashboard-transactions"></div>
    </body>`, {url: 'http://localhost/'});
    Object.assign(globalThis, {window: dom.window, document: dom.window.document});
    const data = {
      gross_assets: 100, immovable_value: 0, invested_value: 0, gic_value: 0,
      liquidity_value: 100, liquidity_by_type: {non_registered: 100}, rrsp_uninvested: 0,
      uninvested_security_value: 0, savings_threshold: 0.025, low_rate_value: 0,
      categories: [{label: 'Test', count: 1, total: 100}],
      maturities: [{institution: 'Test', name: 'GIC', maturity_date: '2027-01-01', amount: 100}],
      recent_transactions: [{transaction_date: '2026-01-01', amount: 100}],
    };
    if (target === 'category') data.categories[0].total = amount;
    else if (target === 'maturity') data.maturities[0].amount = amount;
    else if (target === 'transaction') data.recent_transactions[0].amount = amount;
    else data[target] = amount;
    globalThis.fetch = async () => ({ok: true, json: async () => data});
    await import(`../../static/dashboard/dashboard.mjs?unsafe=${index}`);
    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.match(document.querySelector('#dashboard-metrics .form-message').textContent,
      index % 2 ? /précision fiable/ : /reliable cent precision/);
    assert.equal(document.querySelectorAll('.summary-pill, .dashboard-line, table').length, 0);
    dom.window.close();
  }
  configureTestLocalization();
});

test('dashboard preserves cents near its compatibility precision boundary', async () => {
  configureTestLocalization();
  const dom = new JSDOM(`<!doctype html><body>
    <div id="dashboard-metrics"></div><div id="dashboard-categories"></div>
    <div id="dashboard-liquidity"></div><div id="dashboard-maturities"></div>
    <div id="dashboard-transactions"></div>
  </body>`, {url: 'http://localhost/'});
  Object.assign(globalThis, {window: dom.window, document: dom.window.document});
  globalThis.fetch = async () => ({ok: true, json: async () => ({
    gross_assets: 17592186044415.99, immovable_value: 0, invested_value: 0, gic_value: 0,
    liquidity_value: 0, liquidity_by_type: {non_registered: 0}, rrsp_uninvested: 0,
    uninvested_security_value: 0, savings_threshold: 0.025, low_rate_value: 0,
    categories: [], maturities: [],
    recent_transactions: [{transaction_date: '2026-01-01', amount: -17592186044415.99}],
  })});
  await import('../../static/dashboard/dashboard.mjs?precision-boundary');
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(document.querySelector('#dashboard-metrics strong').textContent, '$17,592,186,044,415.99');
  assert.equal(document.querySelector('#dashboard-transactions td:last-child').textContent, '-$17,592,186,044,415.99');
  dom.window.close();
});

test('missing dashboard facts remain unavailable while explicit zero stays zero', async () => {
  for (const locale of ['en-CA', 'fr-CA']) {
    configureTestLocalization(locale);
    const dom = new JSDOM('<div id="dashboard-metrics"></div><div id="dashboard-categories"></div><div id="dashboard-liquidity"></div><div id="dashboard-maturities"></div><div id="dashboard-transactions"></div>');
    Object.assign(globalThis, {window: dom.window, document: dom.window.document});
    const data = {
      gross_assets: null, immovable_value: 0, invested_value: 0, gic_value: 0,
      liquidity_value: null, liquidity_by_type: {}, rrsp_uninvested: null,
      uninvested_security_value: null, savings_threshold: .025, low_rate_value: null,
      categories: [], maturities: [], recent_transactions: [],
    };
    globalThis.fetch = async () => ({ok: true, json: async () => data});
    await import(`../../static/dashboard/dashboard.mjs?missing=${locale}`);
    await new Promise(resolve => setTimeout(resolve, 0));
    const amounts = [...document.querySelectorAll('#dashboard-metrics strong')];
    assert.equal(amounts[0].textContent, locale === 'en-CA' ? 'Unavailable' : 'Indisponible');
    assert.match(amounts[1].textContent, /0[.,]00/);
    assert.match(document.querySelector('#dashboard-categories').textContent, locale === 'en-CA' ? /No accounts/ : /Aucun compte/);
    assert.equal(document.querySelectorAll('[aria-busy="false"]').length, 5);
    dom.window.close();
  }
  configureTestLocalization();
});

test('HTTP, network and malformed responses clear all stale loading panels', async () => {
  for (const [index, fetcher] of [
    async () => ({ok: false, status: 503, json: async () => ({error: 'Synthetic unavailable'})}),
    async () => {throw new Error('Synthetic network failure');},
    async () => ({ok: true, json: async () => {throw new SyntaxError('Synthetic malformed JSON');}}),
  ].entries()) {
    configureTestLocalization();
    const dom = new JSDOM(['metrics', 'categories', 'liquidity', 'maturities', 'transactions'].map(name => `<div id="dashboard-${name}" aria-busy="true">Loading</div>`).join(''));
    Object.assign(globalThis, {window: dom.window, document: dom.window.document});
    globalThis.fetch = fetcher;
    await import(`../../static/dashboard/dashboard.mjs?all-panel-error=${index}`);
    await new Promise(resolve => setTimeout(resolve, 0));
    assert.equal(document.querySelectorAll('[role="alert"]').length, 1);
    assert.equal(document.querySelectorAll('[aria-busy="true"]').length, 0);
    assert.doesNotMatch(document.body.textContent, /Loading/);
    assert.equal([...document.querySelectorAll('.dashboard-empty')].filter(node => node.textContent === 'Unavailable').length, 4);
    dom.window.close();
  }
});
