// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import test from 'node:test';
import {JSDOM} from 'jsdom';

function waitForTasks() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

test('connections uses the clicked sync controls and restores failures', async () => {
  const dom = new JSDOM('<!doctype html><body><button id="sync-all">Sync all</button><div id="connection-list"></div></body>', {url: 'http://localhost/connections'});
  Object.assign(globalThis, {window: dom.window, document: dom.window.document});
  const syncPayloads = [];
  let failSync = false;
  globalThis.fetch = async (url, options = {}) => {
    if (url === '/api/institutions') return {ok: true, json: async () => ({institutions: [{key: 'broker', display_name: 'Broker', connection: {status_path: '/status', sync_path: '/sync', connect_path: '/connect'}}]})};
    if (url === '/status') return {ok: true, json: async () => ({configured_connections: ['Primary'], authorizations: [{name: 'Primary', access_expires_at: '2026-09-28T22:00:00Z', last_sync_at: null}]})};
    if (url === '/sync') {
      syncPayloads.push(JSON.parse(options.body));
      if (failSync) return {ok: false, json: async () => ({errors: [{error: 'Network failed'}]})};
      return {ok: true, json: async () => ({errors: [], results: [{connection: 'Primary', account_count: 1, balance_count: 1, position_count: 2, transaction_count: 3}]})};
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

  document.querySelector('#sync-all').click();
  await waitForTasks();
  assert.equal(document.querySelector('#sync-all').disabled, false);
  failSync = false;
  document.querySelector('#sync-all').click();
  await waitForTasks();
  await waitForTasks();
  assert.match(document.body.textContent, /Synchronization complete/);
  dom.window.close();
});

test('connections handles an installation with no configured logins', async () => {
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
