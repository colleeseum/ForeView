// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {runButtonAction} from './button-action.mjs';
import {escapeHtml, htmlWithLanguageSpans} from './html.mjs';
import {t, locale} from './i18n.mjs';

const connectionList = document.querySelector('#connection-list');
const syncAllButton = document.querySelector('#sync-all');
const syncAllDefaultText = syncAllButton.dataset.defaultText;
const syncAllBusyText = syncAllButton.dataset.busyText;
let connectedInstitutions = [];

function localizedError(message) {
  const error = new Error(message);
  error.language = locale;
  return error;
}

function rawError(message) {
  const error = new Error(message);
  error.language = 'en-CA';
  return error;
}

function connectionCount(singular, plural, count) {
  return t(`connections.${Number(count) === 1 ? singular : plural}`, {count});
}

function showError(error) {
  const language = error.language || 'en-CA';
  connectionList.insertAdjacentHTML(
    'beforebegin',
    `<p class="connection-notice error" lang="${escapeHtml(language)}" role="alert">${error.html || escapeHtml(error.message)}</p>`,
  );
}

async function loadConnections() {
  const discoveryResponse = await fetch('/api/institutions');
  const discovery = await discoveryResponse.json();
  connectedInstitutions = (discovery.institutions || []).filter((item) => item.connection);
  const states = await Promise.all(connectedInstitutions.map(async (institution) => {
    const response = await fetch(institution.connection.status_path);
    if (!response.ok) {
      throw localizedError(t('connections.status_error', {provider: institution.display_name}));
    }
    return {institution, status: await response.json()};
  }));
  const configured = states.flatMap(({institution, status}) =>
    (status.configured_connections || []).map((name) => ({institution, status, name})));
  if (!configured.length) {
    connectionList.innerHTML = `<div class="empty-panel"><p>${t('connections.none')}</p><p>${escapeHtml(t('connections.configure'))}</p></div>`;
    syncAllButton.disabled = true;
    return;
  }
  const params = new URLSearchParams(window.location.search);
  const providerResult = connectedInstitutions.find((item) => params.has(item.key));
  const result = providerResult ? params.get(providerResult.key) : null;
  const message = params.get('message');
  const notice = result === 'refreshed' ? t('connections.refreshed')
    : result === 'connected' ? escapeHtml(t('connections.saved', {provider: providerResult.display_name}))
    : result === 'error' ? message
      ? htmlWithLanguageSpans(
        ({message: messageToken}) => t('connections.error', {message: messageToken}),
        {message},
      )
      : escapeHtml(t('connections.error', {message: t('connections.unknown')})) : '';
  if (notice) {
    const noticeClass = result === 'error' ? 'connection-notice error' : 'connection-notice';
    connectionList.insertAdjacentHTML('beforebegin', `<p class="${noticeClass}" role="status">${notice}</p>`);
    window.history.replaceState({}, '', window.location.pathname);
  }
  connectionList.innerHTML = configured.map(({institution, status, name}) => {
    const authorization = (status.authorizations || []).find((item) => item.name === name);
    const detail = authorization
      ? [
        escapeHtml(t('connections.connected')),
        escapeHtml(t('connections.valid_until', {time: new Date(authorization.access_expires_at).toLocaleTimeString(locale, {hour: 'numeric', minute: '2-digit'})})),
        escapeHtml(t('connections.last_sync', {time: authorization.last_sync_at ? new Date(authorization.last_sync_at).toLocaleString(locale) : t('connections.never')})),
        authorization.last_sync_error
          ? htmlWithLanguageSpans(
            ({message}) => t('connections.last_failed', {message}),
            {message: authorization.last_sync_error},
          )
          : null,
      ].filter(Boolean).join(' · ')
      : t('connections.not_connected');
    const action = authorization
      ? `<div class="connection-actions"><button class="view-action sync-connection" type="button" data-provider="${escapeHtml(institution.key)}" data-connection="${escapeHtml(name)}">${escapeHtml(t('connections.sync', {provider: institution.display_name, name}))}</button>`
        + `<details class="connection-advanced"><summary>${t('connections.advanced')}</summary><div class="refetch-controls"><label class="refetch-field" title="${escapeHtml(t('connections.refetch_help'))}">${t('connections.refetch_from')} <input class="refetch-date" type="date" data-connection="${escapeHtml(name)}"></label>`
        + `<button class="view-action refetch-connection" type="button" data-provider="${escapeHtml(institution.key)}" data-connection="${escapeHtml(name)}">${t('connections.refetch')}</button></div></details></div>`
      : `<a class="view-action" href="${escapeHtml(institution.connection.connect_path)}?connection=${encodeURIComponent(name)}">${escapeHtml(t('connections.connect', {provider: institution.display_name, name}))}</a>`;
    return `<article class="connection-card"><div><p class="eyebrow">${escapeHtml(institution.display_name)}</p><h2>${escapeHtml(name)}</h2><p class="connection-status">${detail}</p></div>${action}</article>`;
  }).join('');
}

async function sync(provider, connection = null, reload = true, fetchFrom = null) {
  const institution = connectedInstitutions.find((item) => item.key === provider);
  if (!institution) throw localizedError(t('connections.unknown_provider', {provider}));
  const payload = connection ? {connection} : {};
  if (fetchFrom) payload.fetch_from = fetchFrom;
  const response = await fetch(institution.connection.sync_path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
  const data = await response.json();
  if (!response.ok) {
    throw data.errors?.[0]?.error
      ? rawError(data.errors[0].error)
      : localizedError(t('connections.sync_failed'));
  }
  if (data.errors?.length) {
    const spanValues = Object.fromEntries(
      data.errors.map((item, index) => [`error${index}`, item.error]),
    );
    const error = localizedError(t('connections.sync_failed'));
    error.html = htmlWithLanguageSpans((tokens) => {
      const failures = data.errors.map((item, index) => t('connections.failure_detail', {
        connection: item.connection,
        account: item.account ? t('connections.account_detail', {account: item.account}) : '',
        component: item.component || '',
        error: tokens[`error${index}`],
      })).join(' · ');
      return t('connections.partial', {details: failures});
    }, spanValues);
    throw error;
  }
  if (reload) await loadConnections();
  const summary = data.results.map((item) => t('connections.summary', {
    name: item.connection,
    accounts: connectionCount('account_count', 'account_count_plural', item.account_count),
    balances: connectionCount('balance_count', 'balance_count_plural', item.balance_count),
    positions: connectionCount('position_count', 'position_count_plural', item.position_count),
    transactions: connectionCount('transaction_count', 'transaction_count_plural', item.transaction_count),
  })).join(' · ');
  if (reload) connectionList.insertAdjacentHTML('beforebegin', `<p class="connection-notice" role="status">${escapeHtml(t('connections.complete', {summary}))}</p>`);
  return summary;
}

syncAllButton?.addEventListener('click', async () => {
  try {
    syncAllButton.disabled = true;
    syncAllButton.textContent = syncAllBusyText;
    const summaries = await Promise.all(connectedInstitutions.map((item) => sync(item.key, null, false)));
    await loadConnections();
    connectionList.insertAdjacentHTML('beforebegin', `<p class="connection-notice" role="status">${escapeHtml(t('connections.complete', {summary: summaries.filter(Boolean).join(' · ')}))}</p>`);
  } catch (error) {
    showError(error);
  } finally {
    syncAllButton.disabled = false;
    syncAllButton.textContent = syncAllDefaultText;
  }
});

connectionList.addEventListener('click', async (event) => {
  const button = event.target.closest('.sync-connection');
  if (button) {
    try {
      await runButtonAction(button, t('connections.syncing'), () => sync(button.dataset.provider, button.dataset.connection));
    } catch (error) {
      showError(error);
    }
    return;
  }
  const refetch = event.target.closest('.refetch-connection');
  if (refetch) {
    const input = refetch.closest('.connection-actions')?.querySelector('.refetch-date');
    if (!input?.value) {
      showError(localizedError(t('connections.choose_date')));
      return;
    }
    try {
      await runButtonAction(refetch, t('connections.refetching'), () => sync(
        refetch.dataset.provider,
        refetch.dataset.connection,
        true,
        input.value,
      ));
    } catch (error) {
      showError(error);
    }
  }
});
loadConnections().catch((error) => {
  const message = error.language === locale
    ? escapeHtml(error.message)
    : htmlWithLanguageSpans(
      ({message}) => t('connections.load_error', {message}),
      {message: error.message},
    );
  connectionList.innerHTML = `<div class="empty-panel"><p>${message}</p></div>`;
});
