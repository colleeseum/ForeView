// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {initializeAccountDialog, openAccountDialog} from './account-dialog.mjs';
import {loadAssetData, loadPeople} from './accounts-api.mjs';
import {initializeRealEstate} from './accounts-real-estate.mjs';
import {renderAssets} from './accounts-render.mjs';
import {assetState} from './accounts-state.mjs';
import {initializeGicDialog, openGicDialog} from './gic-dialog.mjs';
import {initializeIconActions} from '../shared/icon-actions.mjs';
import {t} from '../shared/i18n.mjs';
import {initializeTableDensity} from '../shared/table-density.mjs';

initializeIconActions();

const tabs = document.querySelectorAll('.view-tab');
let loadState = 'loading';

function syncLocation() {
  const params = new URLSearchParams(window.location.search);
  params.set('tab', assetState.view);
  const query = params.toString();
  window.history.replaceState({}, '', `${window.location.pathname}${query ? `?${query}` : ''}`);
}

function activateTab() {
  tabs.forEach((tab) => {
    const active = tab.dataset.view === assetState.view;
    tab.classList.toggle('active', active);
    tab.setAttribute('aria-pressed', String(active));
  });
  document.querySelectorAll('.view-panel').forEach((panel) => {
    panel.classList.toggle('active', panel.id === 'accounts-table');
  });
}

function render() {
  if (loadState !== 'ready') return;
  renderAssets({openAccount: openAccountDialog, openGic: openGicDialog});
  const content = document.querySelector('#accounts-table-content');
  content.setAttribute('aria-busy', 'false');
  content.querySelectorAll('.table-card').forEach(region => {
    region.tabIndex = 0;
    region.setAttribute('role', 'region');
    region.setAttribute('aria-label', t('accounts.table_region'));
    region.setAttribute('aria-describedby', 'assets-scroll-hint');
  });
  content.querySelectorAll('thead th').forEach(cell => {cell.scope = 'col';});
}

async function reloadAssets() {
  const message = document.querySelector('#assets-message');
  if (message) {
    message.textContent = t('accounts.saved');
    message.hidden = false;
  }
  await loadWorkspace();
}

async function loadWorkspace() {
  const content = document.querySelector('#accounts-table-content');
  const retry = document.querySelector('#retry-assets');
  loadState = 'loading';
  content.textContent = t('accounts.loading');
  content.lang = document.documentElement.lang || 'en-CA';
  content.removeAttribute('role');
  content.setAttribute('aria-busy', 'true');
  if (retry) retry.hidden = true;
  try {
    const [people, data] = await Promise.all([loadPeople(), loadAssetData()]);
    assetState.people = people;
    Object.assign(assetState, data);
    loadState = 'ready';
    render();
  } catch (error) {
    loadState = 'error';
    content.textContent = error.message;
    content.lang = error.language || 'en-CA';
    content.setAttribute('aria-busy', 'false');
    content.setAttribute('role', 'alert');
    if (retry) retry.hidden = false;
  }
}

const density = document.querySelector('#asset-density');
if (density) initializeTableDensity(density, document.querySelector('.fv-assets'), 'foreview.assets.table-density');

tabs.forEach((tab) => tab.addEventListener('click', () => {
  assetState.view = tab.dataset.view;
  syncLocation();
  activateTab();
  render();
}));

initializeAccountDialog(reloadAssets);
initializeGicDialog(reloadAssets);
initializeRealEstate(reloadAssets);
document.querySelector('#reload-assets')?.addEventListener('click', () => window.location.reload());
document.querySelector('#retry-assets')?.addEventListener('click', loadWorkspace);

syncLocation();
activateTab();

loadWorkspace();
