import {initializeAccountDialog, openAccountDialog} from './account-dialog.mjs';
import {loadAssetData, loadPeople} from './accounts-api.mjs';
import {initializeRealEstate} from './accounts-real-estate.mjs';
import {renderAssets} from './accounts-render.mjs';
import {assetState} from './accounts-state.mjs';
import {initializeGicDialog, openGicDialog} from './gic-dialog.mjs';

const tabs = document.querySelectorAll('.view-tab');

function syncLocation() {
  const params = new URLSearchParams(window.location.search);
  params.set('tab', assetState.view);
  const query = params.toString();
  window.history.replaceState({}, '', `${window.location.pathname}${query ? `?${query}` : ''}`);
}

function activateTab() {
  tabs.forEach((tab) => tab.classList.toggle('active', tab.dataset.view === assetState.view));
  document.querySelectorAll('.view-panel').forEach((panel) => {
    panel.classList.toggle('active', panel.id === 'accounts-table');
  });
}

function render() {
  renderAssets({openAccount: openAccountDialog, openGic: openGicDialog});
}

async function reloadAssets() {
  Object.assign(assetState, await loadAssetData());
  render();
}

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

syncLocation();
activateTab();

Promise.all([loadPeople(), loadAssetData()])
  .then(([people, data]) => {
    assetState.people = people;
    Object.assign(assetState, data);
    render();
  })
  .catch((error) => {
    document.querySelector('#accounts-table-content').textContent = error.message;
  });
