// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import test from 'node:test';
import {JSDOM} from 'jsdom';
import {configureTestLocalization} from './localization-fixture.mjs';

function waitForTasks() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

test('connections uses the clicked sync controls and restores failures', async () => {
  configureTestLocalization();
  const dom = new JSDOM('<!doctype html><body><button id="sync-all" data-default-text="Tout synchroniser" data-busy-text="Synchronisation...">Tout synchroniser</button><div id="connection-list"></div></body>', {url: 'http://localhost/connections'});
  Object.assign(globalThis, {window: dom.window, document: dom.window.document});
  const syncPayloads = [];
  let failSync = false;
  globalThis.fetch = async (url, options = {}) => {
    if (url === '/api/institutions') return {ok: true, json: async () => ({institutions: [{key: 'broker', display_name: 'Broker', connection: {status_path: '/status', sync_path: '/sync', connect_path: '/connect'}}]})};
    if (url === '/status') return {ok: true, json: async () => ({configured_connections: ['Primary'], authorizations: [{name: 'Primary', access_expires_at: '2026-09-28T22:00:00Z', last_sync_at: null}]})};
    if (url === '/sync') {
      syncPayloads.push(JSON.parse(options.body));
      if (failSync) return {ok: false, json: async () => ({errors: [{error: 'Network failed'}]})};
      return {ok: true, json: async () => ({errors: [], results: [{connection: 'Primary', account_count: '1', balance_count: '1', position_count: 2, transaction_count: 3}]})};
    }
    throw new Error(`Unexpected fetch: ${url}`);
  };

  await import('../../static/connections.mjs');
  await waitForTasks();
  const list = document.querySelector('#connection-list');
  assert.match(list.textContent, /last successful sync never/);
  assert.equal(list.querySelector('.connection-advanced').open, false);

  list.querySelector('.refetch-connection').click();
  await waitForTasks();
  assert.match(document.body.textContent, /Choose the date/);

  list.querySelector('.refetch-date').value = '2026-01-01';
  list.querySelector('.refetch-connection').click();
  await waitForTasks();
  await waitForTasks();
  assert.deepEqual(syncPayloads.at(-1), {connection: 'Primary', fetch_from: '2026-01-01'});

  failSync = true;
  const syncButton = list.querySelector('.sync-connection');
  syncButton.click();
  await waitForTasks();
  assert.equal(syncButton.disabled, false);
  assert.match(syncButton.textContent, /Sync Broker Primary/);
  assert.match(document.body.textContent, /Network failed/);

  const syncAllButton = document.querySelector('#sync-all');
  syncAllButton.click();
  assert.equal(syncAllButton.textContent, 'Synchronisation...');
  await waitForTasks();
  assert.equal(syncAllButton.disabled, false);
  assert.equal(syncAllButton.textContent, 'Tout synchroniser');
  failSync = false;
  syncAllButton.click();
  assert.equal(syncAllButton.textContent, 'Synchronisation...');
  await waitForTasks();
  await waitForTasks();
  assert.equal(syncAllButton.textContent, 'Tout synchroniser');
  assert.match(document.body.textContent, /Synchronization complete/);
  assert.match(document.body.textContent, /1 account, 1 balance, 2 positions, 3 transactions/);
  dom.window.close();
});

test('connections handles an installation with no configured logins', async () => {
  configureTestLocalization();
  const dom = new JSDOM('<!doctype html><body><button id="sync-all">Sync all</button><div id="connection-list"></div></body>', {url: 'http://localhost/connections'});
  Object.assign(globalThis, {window: dom.window, document: dom.window.document});
  globalThis.fetch = async (url) => {
    if (url === '/api/institutions') return {ok: true, json: async () => ({institutions: [{key: 'broker', display_name: 'Broker', connection: {status_path: '/status'}}]})};
    return {ok: true, json: async () => ({configured_connections: []})};
  };
  await import('../../static/connections.mjs?empty');
  await waitForTasks();
  assert.match(document.querySelector('#connection-list').textContent, /No institutions are configured/);
  assert.equal(document.querySelector('#sync-all').disabled, true);
  dom.window.close();
});

test('connections renders an authorization callback for a disconnected login', async () => {
  configureTestLocalization();
  const dom = new JSDOM('<!doctype html><body><button id="sync-all">Sync all</button><div id="connection-list"></div></body>', {url: 'http://localhost/connections?broker=connected'});
  Object.assign(globalThis, {window: dom.window, document: dom.window.document});
  globalThis.fetch = async (url) => {
    if (url === '/api/institutions') return {ok: true, json: async () => ({institutions: [{key: 'broker', display_name: 'Broker', connection: {status_path: '/status', connect_path: '/connect'}}]})};
    return {ok: true, json: async () => ({configured_connections: ['Secondary'], authorizations: []})};
  };
  await import('../../static/connections.mjs?disconnected');
  await waitForTasks();
  assert.match(document.body.textContent, /Broker connection saved/);
  assert.match(document.querySelector('#connection-list').textContent, /Not connected/);
  assert.equal(document.querySelector('#connection-list a').getAttribute('href'), '/connect?connection=Secondary');
  assert.equal(dom.window.location.search, '');
  dom.window.close();
});

test('connections preserve English boundaries inside the French interface', async () => {
  configureTestLocalization('fr-CA');
  const dom = new JSDOM('<!doctype html><body><button id="sync-all" data-default-text="Tout synchroniser" data-busy-text="Synchronisation...">Tout synchroniser</button><div id="connection-list"></div></body>', {url: 'http://localhost/connections'});
  Object.assign(globalThis, {window: dom.window, document: dom.window.document});
  globalThis.fetch = async (url) => {
    if (url === '/api/institutions') {
      return {ok: true, json: async () => ({institutions: [{
        key: 'broker', display_name: 'Broker',
        connection: {status_path: '/status', sync_path: '/sync', connect_path: '/connect'},
      }]})};
    }
    if (url === '/status') {
      return {ok: true, json: async () => ({
        configured_connections: ['Primary'],
        authorizations: [{
          name: 'Primary', access_expires_at: '2026-09-28T22:00:00Z',
          last_sync_at: null, last_sync_error: 'Token refresh failed',
        }],
      })};
    }
    if (url === '/sync') {
      return {ok: true, json: async () => ({
        results: [],
        errors: [{connection: 'Primary', account: 'A1', component: 'balances', error: 'Remote API failed'}],
      })};
    }
    throw new Error(`Unexpected fetch: ${url}`);
  };

  await import(`../../static/connections.mjs?language-boundaries=${Date.now()}`);
  await waitForTasks();
  const status = document.querySelector('.connection-status');
  assert.match(status.textContent, /dernière tentative échouée/);
  assert.equal(status.querySelector('[lang="en-CA"]').textContent, 'Token refresh failed');

  document.querySelector('.sync-connection').click();
  await waitForTasks();
  const notice = document.querySelector('.connection-notice.error');
  assert.equal(notice.lang, 'fr-CA');
  assert.match(notice.textContent, /Synchronisation partiellement réussie/);
  assert.equal(notice.querySelector('[lang="en-CA"]').textContent, 'Remote API failed');
  configureTestLocalization();
  dom.window.close();
});
