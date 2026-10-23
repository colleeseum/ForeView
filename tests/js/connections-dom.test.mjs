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

  await import('../../static/connections/connections.mjs');
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
  await import('../../static/connections/connections.mjs?empty');
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
  await import('../../static/connections/connections.mjs?disconnected');
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

  await import(`../../static/connections/connections.mjs?language-boundaries=${Date.now()}`);
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

test('connections isolates unavailable providers and preserves recovery after localized failures', async () => {
  for (const language of ['en-CA', 'fr-CA']) {
    configureTestLocalization(language);
    const dom = new JSDOM('<!doctype html><body><button id="sync-all" data-default-text="Sync all" data-busy-text="Busy">Sync all</button><div id="connection-list"></div></body>', {url: 'http://localhost/connections'});
    Object.assign(globalThis, {window: dom.window, document: dom.window.document});
    let posts = 0;
    const error = language === 'fr-CA' ? 'Service indisponible <secret>' : 'Service unavailable <secret>';
    globalThis.fetch = async (url, options = {}) => {
      if (url === '/api/institutions') return {ok: true, json: async () => ({institutions: [
        {key: 'broker', display_name: 'Broker', connection: {status_path: '/status', sync_path: '/sync', connect_path: '/connect'}},
        {key: 'offline', display_name: 'Offline provider', connection: {status_path: '/offline'}},
      ]})};
      if (url === '/offline') throw new Error('private upstream diagnostic');
      if (url === '/status') return {ok: true, json: async () => ({configured_connections: ['Broken & saved', 'Healthy'], authorizations: [
        {name: 'Broken & saved', error, error_code: 'questrade_refresh_unavailable', error_language: language},
        {name: 'Healthy', access_expires_at: '2026-10-20T20:00:00Z'},
      ]})};
      if (url === '/sync') {
        assert.equal(options.method, 'POST');
        posts += 1;
        return {ok: false, json: async () => ({errors: [{error, error_language: language}], results: []})};
      }
      throw new Error('Unexpected fetch');
    };
    await import(`../../static/connections/connections.mjs?recovery=${language}`);
    await waitForTasks();
    assert.equal(document.querySelectorAll('.connection-card').length, 3);
    assert.equal(posts, 0);
    const retry = document.querySelector('[data-reload-connections]');
    retry.click();
    retry.dispatchEvent(new dom.window.Event('click', {bubbles: true}));
    await waitForTasks(); await waitForTasks();
    assert.equal(posts, 0, 'Retrying status never refreshes or synchronizes credentials');
    assert.equal(document.activeElement.dataset.provider, 'offline', 'Focus follows the replaced retry control');
    assert.doesNotMatch(document.body.textContent, /private upstream/);
    assert.equal(document.querySelector('.connection-status span').lang, language);
    assert.equal(document.querySelector('secret'), null);
    const reconnect = document.querySelector('.connection-actions a');
    assert.equal(reconnect.getAttribute('href'), '/connect?connection=Broken%20%26%20saved');
    assert.match(reconnect.textContent, /Reconnect/);
    const button = document.querySelector('.sync-connection');
    button.click();
    await waitForTasks();
    await waitForTasks();
    assert.equal(posts, 1);
    assert.equal(button.disabled, false);
    assert.equal(document.querySelector('.sync-connection').disabled, false);
    assert.equal(document.querySelector('.connection-notice.error').lang, language);
    assert.equal(document.querySelectorAll('.connection-card').length, 3);
    dom.window.close();
  }
  configureTestLocalization();
});

test('connections displays provider failures without a misleading unconfigured message', async () => {
  configureTestLocalization();
  const dom = new JSDOM('<button id="sync-all">Sync all</button><div id="connection-list"></div>', {url: 'http://localhost/connections'});
  Object.assign(globalThis, {window: dom.window, document: dom.window.document});
  globalThis.fetch = async (url) => url === '/api/institutions'
    ? {ok: true, json: async () => ({institutions: [{key: 'broker', display_name: 'Broker', connection: {status_path: '/status'}}]})}
    : {ok: false};
  await import('../../static/connections/connections.mjs?all-unavailable');
  await waitForTasks();
  assert.match(document.body.textContent, /Could not load Broker status/);
  assert.doesNotMatch(document.body.textContent, /No institutions are configured/);
  assert.equal(document.querySelector('#sync-all').disabled, true);
  dom.window.close();
});

test('Sync all excludes unavailable providers and retains successes when another sync fails', async () => {
  configureTestLocalization();
  const dom = new JSDOM('<button id="sync-all" data-default-text="Sync all" data-busy-text="Busy">Sync all</button><div id="connection-list"></div>', {url: 'http://localhost/connections'});
  Object.assign(globalThis, {window: dom.window, document: dom.window.document});
  const synced = [];
  let failAvailableProvider = false;
  let failDiscovery = false;
  globalThis.fetch = async (url) => {
    if (url === '/api/institutions' && failDiscovery) throw new Error('Discovery unavailable');
    if (url === '/api/institutions') return {ok: true, json: async () => ({institutions: ['healthy', 'failing', 'offline', 'empty'].map((key) => ({
      key, display_name: key,
      connection: {status_path: `/status/${key}`, sync_path: `/sync/${key}`, connect_path: `/connect/${key}`},
    }))})};
    if (url === '/status/offline') return {ok: false};
    if (url.startsWith('/status/')) {
      const name = url.split('/').at(-1);
      return {ok: true, json: async () => ({configured_connections: name === 'empty' ? [] : [name], authorizations: [{name}]})};
    }
    synced.push(url);
    if (url === '/sync/offline' || url === '/sync/empty') throw new Error('Unavailable provider must not be synced');
    if (url === '/sync/failing' && failAvailableProvider) throw new Error('Network failed');
    return {ok: true, json: async () => ({errors: [], results: [{connection: url.split('/').at(-1), account_count: 1, balance_count: 0, position_count: 0, transaction_count: 0}]})};
  };
  await import('../../static/connections/connections.mjs?sync-all-isolation');
  await waitForTasks();
  const button = document.querySelector('#sync-all');
  button.click();
  await waitForTasks();
  await waitForTasks();
  assert.deepEqual(synced.sort(), ['/sync/failing', '/sync/healthy']);
  assert.match(document.querySelector('.connection-notice').textContent, /healthy: 1 account/);
  assert.equal(document.querySelector('.connection-notice.error'), null);
  failAvailableProvider = true;
  synced.length = 0;
  button.click();
  await waitForTasks();
  await waitForTasks();
  assert.deepEqual(synced.sort(), ['/sync/failing', '/sync/healthy']);
  const successes = [...document.querySelectorAll('.connection-notice:not(.error)')];
  assert.match(successes[0].textContent, /healthy: 1 account/);
  assert.match(document.querySelector('.connection-notice.error').textContent, /Network failed/);
  assert.equal(document.querySelectorAll('.connection-card').length, 3);
  assert.equal(button.disabled, false);
  assert.equal(button.textContent, 'Sync all');
  failDiscovery = true;
  button.click();
  await waitForTasks();
  await waitForTasks();
  assert.match(document.querySelector('.connection-notice:not(.error)').textContent, /healthy: 1 account/);
  assert.match(document.body.textContent, /Discovery unavailable/);
  assert.equal(button.disabled, false);
  dom.window.close();
});

test('partial provider responses retain successful login summaries alongside localized failures', async () => {
  for (const language of ['en-CA', 'fr-CA']) {
    configureTestLocalization(language);
    const dom = new JSDOM('<button id="sync-all" data-default-text="Sync all" data-busy-text="Busy">Sync all</button><div id="connection-list"></div>', {url: 'http://localhost/connections'});
    Object.assign(globalThis, {window: dom.window, document: dom.window.document});
    let resultCount = 1;
    let posts = 0;
    const failure = language === 'fr-CA' ? 'Autorisation refusée <secret>' : 'Authorization rejected <secret>';
    globalThis.fetch = async (url) => {
      if (url === '/api/institutions') return {ok: true, json: async () => ({institutions: [{key: 'broker', display_name: 'Broker', connection: {status_path: '/status', sync_path: '/sync', connect_path: '/connect'}}]})};
      if (url === '/status') return {ok: true, json: async () => ({configured_connections: ['Good', 'Bad'], authorizations: [{name: 'Good'}, {name: 'Bad'}]})};
      posts += 1;
      return {ok: true, status: 207, json: async () => ({
        results: resultCount ? [{connection: 'Good', account_count: 1, balance_count: 2, position_count: 3, transaction_count: 4}] : [],
        errors: [{connection: 'Bad', error: failure, error_language: language}],
      })};
    };
    await import(`../../static/connections/connections.mjs?partial-provider=${language}`);
    await waitForTasks();
    const all = document.querySelector('#sync-all');
    for (const action of [() => all.click(), () => document.querySelector('.sync-connection').click()]) {
      document.querySelectorAll('.connection-notice').forEach((node) => node.remove());
      action();
      await waitForTasks();
      await waitForTasks();
      assert.match(document.querySelector('.connection-notice:not(.error)').textContent, /Good/);
      const error = document.querySelector('.connection-notice.error');
      assert.equal(error.lang, language);
      assert.equal(error.querySelector('span').lang, language);
      assert.match(error.textContent, /Bad/);
      assert.ok(error.textContent.includes(failure));
      assert.equal(document.querySelector('secret'), null);
      assert.equal(all.disabled, false);
      assert.equal(document.querySelector('.sync-connection').disabled, false);
    }
    assert.equal(posts, 2);
    resultCount = 0;
    document.querySelectorAll('.connection-notice').forEach((node) => node.remove());
    all.click();
    await waitForTasks();
    await waitForTasks();
    assert.equal(document.querySelector('.connection-notice:not(.error)'), null);
    assert.ok(document.querySelector('.connection-notice.error'));
    dom.window.close();
  }
  configureTestLocalization();
});
