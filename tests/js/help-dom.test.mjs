import assert from 'node:assert/strict';
import test from 'node:test';

import {JSDOM} from 'jsdom';

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

const catalog = {
  tooltips: [
    {key: 'salary-rate', title: 'Salary rate', body: 'Income minus bonus.'},
  ],
  articles: [
    {key: 'income', title: 'Employment income', summary: 'Annual facts.', body: 'Income article.', keywords: ['salary']},
    {key: 'transaction-import', title: 'Bank imports', summary: 'Load statements.', body: 'Bank article.', keywords: ['PDF', 'bank']},
    {key: 'income-source-ufile', title: 'Loading UFile', summary: 'Get a T1.', body: 'UFile article.', keywords: ['T1', 'UFile']},
  ],
};

function installDom(url = 'http://localhost/income') {
  const dom = new JSDOM(`<!doctype html><body><main><header><h1>Income</h1></header></main>
    <button data-help-tooltip="salary-rate">?</button>
    <button data-help-article="income-source-ufile">UFile help</button></body>`, {url});
  Object.assign(globalThis, {window: dom.window, document: dom.window.document});
  return dom;
}

test('help provides quick tooltips, searchable full help, and contextual articles', async () => {
  const dom = installDom();
  globalThis.fetch = async () => ({ok: true, json: async () => catalog});
  await import(`../../static/help.mjs?help=${Date.now()}`);
  await tick();

  const fullHelp = document.querySelector('.full-help-button');
  assert.ok(fullHelp);
  fullHelp.click();
  await tick();
  assert.equal(document.querySelector('.help-drawer-backdrop').hidden, false);
  assert.equal(document.querySelector('.help-article h2').textContent, 'Employment income');

  const search = document.querySelector('#help-search');
  search.value = 'bank';
  search.dispatchEvent(new dom.window.Event('input', {bubbles: true}));
  await tick();
  assert.equal(document.querySelector('.help-article h2').textContent, 'Bank imports');
  assert.equal(document.querySelectorAll('[data-help-result]').length, 1);

  document.querySelector('[data-help-article="income-source-ufile"]').click();
  await tick();
  assert.equal(document.querySelector('.help-article h2').textContent, 'Loading UFile');

  document.querySelector('[data-help-tooltip="salary-rate"]').click();
  await tick();
  assert.equal(document.querySelector('.help-tooltip').hidden, false);
  assert.match(document.querySelector('.help-tooltip').textContent, /Income minus bonus/);

  document.dispatchEvent(new dom.window.KeyboardEvent('keydown', {key: 'Escape'}));
  assert.equal(document.querySelector('.help-tooltip').hidden, true);
  assert.equal(document.querySelector('.help-drawer-backdrop').hidden, true);
  dom.window.close();
});

test('full help reports a catalog loading failure', async () => {
  const dom = installDom('http://localhost/about');
  globalThis.fetch = async () => ({ok: false, json: async () => ({error: 'Unavailable'})});
  await import(`../../static/help.mjs?failure=${Date.now()}`);
  document.querySelector('.full-help-button').click();
  await tick();
  assert.equal(document.querySelector('.help-article h2').textContent, 'Help unavailable');
  assert.equal(document.querySelector('.help-article-body').textContent, 'Unavailable');
  dom.window.close();
});
