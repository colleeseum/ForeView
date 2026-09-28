import assert from 'node:assert/strict';
import test from 'node:test';
import {JSDOM} from 'jsdom';

test('dashboard renders escaped financial summaries', async () => {
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

  await import('../../static/dashboard.mjs');
  await new Promise((resolve) => setTimeout(resolve, 0));

  assert.match(document.querySelector('#dashboard-metrics').textContent, /Gross assets/);
  assert.match(document.querySelector('#dashboard-liquidity').textContent, /RRSP uninvested/);
  assert.equal(document.body.innerHTML.includes(attack), false);
  assert.match(document.body.innerHTML, /&lt;img/);
  dom.window.close();
});

test('dashboard renders empty activity states', async () => {
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
  await import('../../static/dashboard.mjs?empty');
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.match(document.querySelector('#dashboard-categories').textContent, /2 accounts/);
  assert.match(document.querySelector('#dashboard-maturities').textContent, /No maturity dates/);
  assert.match(document.querySelector('#dashboard-transactions').textContent, /No transactions/);
  dom.window.close();
});
