import {runButtonAction} from './button-action.mjs';
import {escapeHtml} from './html.mjs';

const connectionList = document.querySelector('#connection-list');
const syncAllButton = document.querySelector('#sync-all');
let connectedInstitutions = [];

async function loadConnections() {
  const discoveryResponse = await fetch('/api/institutions');
  const discovery = await discoveryResponse.json();
  connectedInstitutions = (discovery.institutions || []).filter((item) => item.connection);
  const states = await Promise.all(connectedInstitutions.map(async (institution) => {
    const response = await fetch(institution.connection.status_path);
    if (!response.ok) throw new Error(`Could not load ${institution.display_name} status`);
    return {institution, status: await response.json()};
  }));
  const configured = states.flatMap(({institution, status}) =>
    (status.configured_connections || []).map((name) => ({institution, status, name})));
  if (!configured.length) {
    connectionList.innerHTML = '<div class="empty-panel"><p>No institutions are configured yet.</p><p>Add a connection in <code>finance.config.json</code>, then restart the server.</p></div>';
    syncAllButton.disabled = true;
    return;
  }
  const params = new URLSearchParams(window.location.search);
  const providerResult = connectedInstitutions.find((item) => params.has(item.key));
  const result = providerResult ? params.get(providerResult.key) : null;
  const message = params.get('message');
  const notice = result === 'refreshed' ? 'Connection refreshed automatically.'
    : result === 'connected' ? `${providerResult.display_name} connection saved.`
    : result === 'error' ? `Connection error: ${message || 'Unknown error'}` : '';
  if (notice) {
    const noticeClass = result === 'error' ? 'connection-notice error' : 'connection-notice';
    connectionList.insertAdjacentHTML('beforebegin', `<p class="${noticeClass}" role="status">${escapeHtml(notice)}</p>`);
    window.history.replaceState({}, '', window.location.pathname);
  }
  connectionList.innerHTML = configured.map(({institution, status, name}) => {
    const authorization = (status.authorizations || []).find((item) => item.name === name);
    const detail = authorization
      ? `Connected · token valid until ${escapeHtml(new Date(authorization.access_expires_at).toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'}))} · last successful sync ${authorization.last_sync_at ? escapeHtml(new Date(authorization.last_sync_at).toLocaleString()) : 'never'}${authorization.last_sync_error ? ` · last attempt failed: ${escapeHtml(authorization.last_sync_error)}` : ''}`
      : 'Not connected';
    const action = authorization
      ? `<div class="connection-actions"><button class="view-action sync-connection" type="button" data-provider="${escapeHtml(institution.key)}" data-connection="${escapeHtml(name)}">Sync ${escapeHtml(institution.display_name)} ${escapeHtml(name)}</button>`
        + `<details class="connection-advanced"><summary>Advanced</summary><div class="refetch-controls"><label class="refetch-field" title="Fetch this login's activity again from a date, for example when a reconciled balance no longer matches. Already-imported activity is skipped.">Re-fetch from <input class="refetch-date" type="date" data-connection="${escapeHtml(name)}"></label>`
        + `<button class="view-action refetch-connection" type="button" data-provider="${escapeHtml(institution.key)}" data-connection="${escapeHtml(name)}">Re-fetch</button></div></details></div>`
      : `<a class="view-action" href="${escapeHtml(institution.connection.connect_path)}?connection=${encodeURIComponent(name)}">Connect ${escapeHtml(institution.display_name)} ${escapeHtml(name)}</a>`;
    return `<article class="connection-card"><div><p class="eyebrow">${escapeHtml(institution.display_name)}</p><h2>${escapeHtml(name)}</h2><p class="connection-status">${detail}</p></div>${action}</article>`;
  }).join('');
}

async function sync(provider, connection = null, reload = true, fetchFrom = null) {
  const institution = connectedInstitutions.find((item) => item.key === provider);
  if (!institution) throw new Error(`Unknown connection provider: ${provider}`);
  const payload = connection ? {connection} : {};
  if (fetchFrom) payload.fetch_from = fetchFrom;
  const response = await fetch(institution.connection.sync_path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.errors?.[0]?.error || 'Synchronization failed');
  if (data.errors?.length) {
    const failures = data.errors.map((item) => `${item.connection}${item.account ? ` account ${item.account}` : ''}${item.component ? ` ${item.component}` : ''}: ${item.error}`).join(' · ');
    throw new Error(`Synchronization was only partially successful. ${failures}`);
  }
  if (reload) await loadConnections();
  const summary = data.results.map((item) => `${item.connection}: ${item.account_count} accounts, ${item.balance_count} balances, ${item.position_count} positions, ${item.transaction_count} transactions`).join(' · ');
  if (reload) connectionList.insertAdjacentHTML('beforebegin', `<p class="connection-notice" role="status">Synchronization complete: ${escapeHtml(summary)}</p>`);
  return summary;
}

syncAllButton?.addEventListener('click', async () => {
  try {
    syncAllButton.disabled = true;
    syncAllButton.textContent = 'Syncing...';
    const summaries = await Promise.all(connectedInstitutions.map((item) => sync(item.key, null, false)));
    await loadConnections();
    connectionList.insertAdjacentHTML('beforebegin', `<p class="connection-notice" role="status">Synchronization complete: ${escapeHtml(summaries.filter(Boolean).join(' · '))}</p>`);
  } catch (error) {
    connectionList.insertAdjacentHTML('beforebegin', `<p class="connection-notice error" role="alert">${escapeHtml(error.message)}</p>`);
  } finally {
    syncAllButton.disabled = false;
    syncAllButton.textContent = 'Sync all';
  }
});
function showError(error) {
  connectionList.insertAdjacentHTML('beforebegin', `<p class="connection-notice error" role="alert">${escapeHtml(error.message)}</p>`);
}

connectionList.addEventListener('click', async (event) => {
  const button = event.target.closest('.sync-connection');
  if (button) {
    try {
      await runButtonAction(button, 'Syncing...', () => sync(button.dataset.provider, button.dataset.connection));
    } catch (error) {
      showError(error);
    }
    return;
  }
  const refetch = event.target.closest('.refetch-connection');
  if (refetch) {
    const input = refetch.closest('.connection-actions')?.querySelector('.refetch-date');
    if (!input?.value) {
      showError(new Error('Choose the date to re-fetch activity from.'));
      return;
    }
    try {
      await runButtonAction(refetch, 'Re-fetching...', () => sync(
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
loadConnections().catch((error) => { connectionList.innerHTML = `<div class="empty-panel"><p>Could not load connections: ${escapeHtml(error.message)}</p></div>`; });
