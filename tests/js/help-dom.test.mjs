// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import test from 'node:test';

import {JSDOM} from 'jsdom';
import {configureTestLocalization} from './localization-fixture.mjs';

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

const catalog = {
  language: 'en-CA',
  tooltips: [
    {key: 'salary-rate', title: 'Salary rate', body: 'Income minus bonus.'},
  ],
  articles: [
    {key: 'income', title: 'Employment income', summary: 'Annual facts.', body: 'Income article.', keywords: ['salary']},
    {key: 'expenses', title: 'Expenses', summary: 'Household spending.', body: 'Expenses article.', keywords: ['spending']},
    {key: 'transaction-import', title: 'Bank imports', summary: 'Load statements.', body: 'Bank article.', keywords: ['PDF', 'bank']},
    {key: 'income-source-ufile', title: 'Loading UFile', summary: 'Get a T1.', body: 'UFile article.', keywords: ['T1', 'UFile']},
  ],
  categories: [
    {key: 'financial', parent: null, title: 'Financial records', order: 0},
    {key: 'summary', parent: 'financial', title: 'Summary', order: 0},
    {key: 'income', parent: 'financial', title: 'Income', order: 1},
    {key: 'expenses', parent: 'financial', title: 'Expenses', order: 2},
    {key: 'imports', parent: 'financial', title: 'Imports', order: 3},
    {key: 'tax-documents', parent: 'income', title: 'Tax documents', order: 0},
  ],
};
// The API now declares categories. Keep the existing behavioral expectations,
// while making the fixture conform to that additive catalog contract.
catalog.articles.forEach((article, index) => {
  article.category = ({'transaction-import': 'imports', 'income-source-ufile': 'tax-documents'})[article.key] || article.key;
  article.order = index;
});
catalog.articles.push({key: 'summary', category: 'summary', title: 'Financial summary', summary: 'Overview', body: 'Summary article', order: -1});
catalog.categories.push({key: 'connections', parent: null, title: 'Connections', order: 1});
catalog.articles.push({key: 'connections', category: 'connections', title: 'Institution connections', summary: 'Connect', body: 'Connections article'});

function installDom(url = 'http://localhost/income', pageArticle = null, locale = 'en-CA') {
  configureTestLocalization(locale);
  const helpAttribute = pageArticle ? ` data-help-article="${pageArticle}"` : '';
  const dom = new JSDOM(`<!doctype html><body><main><header${helpAttribute}><h1>Income</h1></header></main>
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

  search.value = 'no-matching-topic';
  search.dispatchEvent(new dom.window.Event('input', {bubbles: true}));
  await tick();
  assert.equal(document.querySelectorAll('[data-help-result]').length, 0);
  assert.equal(document.querySelector('.help-article h2').textContent, 'No matching help');

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

test('full help opens the Expenses article from the Expenses page', async () => {
  const dom = installDom('http://localhost/expenses?year=2026', 'expenses');
  globalThis.fetch = async () => ({ok: true, json: async () => catalog});
  await import(`../../static/help.mjs?expenses=${Date.now()}`);

  document.querySelector('.full-help-button').click();
  await tick();

  assert.equal(document.querySelector('.help-article h2').textContent, 'Expenses');
  assert.equal(
    document.querySelector('[data-help-result="expenses"]').classList.contains('active'),
    true,
  );
  dom.window.close();
});

test('full help reports a catalog loading failure', async () => {
  const dom = installDom('http://localhost/about', null, 'fr-CA');
  globalThis.fetch = async () => ({ok: false, json: async () => ({error: 'Unavailable'})});
  await import(`../../static/help.mjs?failure=${Date.now()}`);
  document.querySelector('.full-help-button').click();
  await tick();
  assert.equal(document.querySelector('.help-article h2').textContent, 'Aide indisponible');
  assert.equal(document.querySelector('.help-article-body').textContent, 'Unavailable');
  assert.equal(document.querySelector('.help-article-body').lang, 'en-CA');
  configureTestLocalization();
  dom.window.close();
});

test('full help localizes its browser-generated controls', async () => {
  const dom = installDom('http://localhost/income', null, 'fr-CA');
  globalThis.fetch = async () => ({ok: true, json: async () => catalog});
  await import(`../../static/help.mjs?french=${Date.now()}`);

  const fullHelp = document.querySelector('.full-help-button');
  assert.equal(fullHelp.title, 'Aide complète');
  fullHelp.click();
  await tick();
  assert.equal(document.querySelector('#full-help-title').textContent, 'Aide');
  assert.equal(document.querySelector('#help-search').placeholder, 'Rechercher par mot-clé');
  assert.equal(document.querySelector('.help-results').lang, 'en-CA');
  assert.equal(document.querySelector('.help-article h2').lang, 'en-CA');
  assert.equal(document.querySelector('.help-article-summary').lang, 'en-CA');
  assert.equal(document.querySelector('.help-article-body').lang, 'en-CA');
  document.querySelector('[data-help-tooltip="salary-rate"]').click();
  await tick();
  assert.equal(document.querySelector('.help-tooltip').lang, 'en-CA');
  configureTestLocalization();
  dom.window.close();
});

test('hierarchy expands the page and contextual branches, and search retains their paths', async () => {
  const dom = installDom('http://localhost/');
  globalThis.fetch = async () => ({ok: true, json: async () => catalog});
  await import('../../static/help.mjs?hierarchy');
  document.querySelector('.full-help-button').click();
  await tick();
  assert.equal(document.querySelector('.help-article h2').textContent, 'Financial summary');
  const summary = document.querySelector('[data-help-result="summary"]');
  assert.equal(summary.closest('details').open, true);
  assert.equal(summary.closest('details').parentElement.closest('details').open, true);
  document.querySelector('[data-help-article="income-source-ufile"]').click();
  await tick();
  const provider = document.querySelector('[data-help-result="income-source-ufile"]');
  assert.equal(provider.closest('details').open, true);
  assert.equal(provider.closest('details').parentElement.closest('details').open, true);
  const search = document.querySelector('#help-search');
  search.value = 'Tax documents';
  search.dispatchEvent(new dom.window.Event('input'));
  await tick();
  assert.equal(document.querySelector('[data-help-result] small').textContent,
    'Financial records › Income › Tax documents');
  search.value = '';
  search.dispatchEvent(new dom.window.Event('input'));
  await tick();
  assert.ok(document.querySelector('details'));
  dom.window.close();
});

test('Escape restores focus only for open help and does not close an underlying dialog', async () => {
  const dom = installDom();
  let underlyingEscapes = 0;
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') underlyingEscapes++; });
  globalThis.fetch = async () => ({ok: true, json: async () => catalog});
  await import('../../static/help.mjs?focus');
  const opener = document.querySelector('.full-help-button');
  opener.focus();
  opener.click();
  await tick();
  const drawer = document.querySelector('.help-drawer');
  const close = document.querySelector('.help-drawer-close');
  const search = document.querySelector('#help-search');
  // jsdom has no layout; expose the two controls for the focus-trap regression.
  close.getClientRects = search.getClientRects = () => [{}];
  search.focus();
  search.dispatchEvent(new dom.window.KeyboardEvent('keydown', {key: 'Tab', bubbles: true, cancelable: true}));
  assert.equal(document.activeElement, close);
  close.dispatchEvent(new dom.window.KeyboardEvent('keydown', {key: 'Tab', shiftKey: true, bubbles: true, cancelable: true}));
  assert.equal(document.activeElement, search);
  drawer.dispatchEvent(new dom.window.KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
  assert.equal(document.activeElement, opener);
  assert.equal(underlyingEscapes, 0);
  const other = document.querySelector('[data-help-tooltip]');
  other.focus();
  document.dispatchEvent(new dom.window.KeyboardEvent('keydown', {key: 'Escape'}));
  assert.equal(document.activeElement, other);
  assert.equal(underlyingEscapes, 1);
  dom.window.close();
});

test('closing help while its catalog loads does not reclaim focus after the response', async () => {
  const dom = installDom();
  let resolve;
  globalThis.fetch = () => new Promise((done) => { resolve = done; });
  await import('../../static/help.mjs?delayed');
  const opener = document.querySelector('.full-help-button');
  opener.focus();
  opener.click();
  assert.equal(document.activeElement, document.querySelector('#help-search'));
  document.querySelector('.help-drawer-close').click();
  resolve({ok: true, json: async () => catalog});
  await tick();
  assert.equal(document.activeElement, opener);
  assert.equal(document.querySelector('.help-drawer-backdrop').hidden, true);
  assert.equal(document.querySelectorAll('[data-help-result]').length, 0);
  dom.window.close();
});

test('article order and escaping apply inside category branches', async () => {
  const dom = installDom();
  const attack = '<img src=x onerror=alert(1)>';
  const ordered = {...catalog, articles: [
    {key: 'later', category: 'income', title: 'Later', summary: '', body: '', order: 9},
    {key: 'income', category: 'income', title: attack, summary: attack, body: attack, order: 1},
  ]};
  globalThis.fetch = async () => ({ok: true, json: async () => ordered});
  await import('../../static/help.mjs?ordered');
  document.querySelector('.full-help-button').click();
  await tick();
  assert.deepEqual([...document.querySelectorAll('[data-help-result]')].map((button) => button.dataset.helpResult), ['income', 'later']);
  assert.equal(document.querySelector('.help-article h2').textContent, attack);
  assert.equal(document.querySelector('.help-drawer img'), null);
  document.querySelector('[data-help-result="later"]').click();
  document.querySelector('.help-drawer-close').click();
  await tick();
  assert.equal(document.querySelector('.help-article h2').textContent, attack);
  document.querySelector('.full-help-button').click();
  await tick();
  document.querySelector('[data-help-result="later"]').click();
  await tick();
  assert.equal(document.querySelector('.help-article h2').textContent, 'Later');
  dom.window.close();
});

test('a newer context request wins over an older pending open', async () => {
  const dom = installDom();
  let resolve;
  globalThis.fetch = () => new Promise((done) => { resolve = done; });
  await import('../../static/help.mjs?newer-request');
  document.querySelector('.full-help-button').focus();
  document.querySelector('.full-help-button').click();
  window.openContextHelp('income-source-ufile');
  resolve({ok: true, json: async () => catalog});
  await tick();
  assert.equal(document.querySelector('.help-article h2').textContent, 'Loading UFile');
  document.querySelector('.help-drawer-close').click();
  assert.equal(document.activeElement, document.querySelector('.full-help-button'));
  dom.window.close();
});

test('search during a pending failed catalog shows the localized error', async () => {
  const dom = installDom();
  let resolve;
  globalThis.fetch = () => new Promise((done) => { resolve = done; });
  await import('../../static/help.mjs?search-failure');
  document.querySelector('.full-help-button').click();
  const search = document.querySelector('#help-search');
  search.value = 'income';
  search.dispatchEvent(new dom.window.Event('input'));
  resolve({ok: false, json: async () => ({error: 'Unavailable'})});
  await tick();
  assert.equal(document.querySelector('.help-article h2').textContent, 'Help unavailable');
  dom.window.close();
});

test('Connections page opens connection help rather than statement imports', async () => {
  const dom = installDom('http://localhost/connections');
  globalThis.fetch = async () => ({ok: true, json: async () => catalog});
  await import('../../static/help.mjs?connections-page');
  document.querySelector('.full-help-button').click();
  await tick();
  assert.equal(document.querySelector('.help-article h2').textContent, 'Institution connections');
  assert.equal(document.querySelector('[data-help-result="connections"]').closest('details').open, true);
  dom.window.close();
});
