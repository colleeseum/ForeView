import {saveJson} from './accounts-api.mjs';
import {money} from './accounts-format.mjs';
import {assetState} from './accounts-state.mjs';
import {formSignature, showError} from './form-state.mjs';
import {
  ownershipSignature,
  ownershipTotal,
  renderOwnershipFields,
  selectedOwners,
} from './ownership-fields.mjs';

const dialog = document.querySelector('#real-estate-dialog');
const form = document.querySelector('#real-estate-dialog-form');
const title = document.querySelector('#real-estate-dialog-title');
const message = document.querySelector('#real-estate-dialog-message');
const ownerFields = document.querySelector('#real-estate-owner-fields');
const ownerTotal = document.querySelector('#real-estate-owner-total');
const saveButton = form.querySelector('button[type="submit"]');

let baseline = '';
let editingId = null;
let saved = async () => {};

function signature() {
  return formSignature(form, ownershipSignature(ownerFields));
}

function updateSaveButton() {
  const total = ownershipTotal(ownerFields);
  ownerTotal.textContent = `Selected ownership: ${total.toFixed(2)}%${Math.abs(total - 100) < 0.01 ? '' : ' · must equal 100%'}`;
  ownerTotal.classList.toggle('error', Math.abs(total - 100) >= 0.01);
  saveButton.disabled = signature() === baseline || Math.abs(total - 100) >= 0.01;
}

function openRealEstateDialog(assetId = null) {
  editingId = assetId;
  const asset = assetState.realEstateAssets.find((item) => item.id === assetId);
  title.textContent = asset ? 'Edit real-estate asset' : 'Add real-estate asset';
  message.textContent = '';
  message.classList.remove('error');
  form.reset();
  form.valuation_date.value = new Date().toISOString().slice(0, 10);
  if (asset) {
    form.name.value = asset.name || '';
    form.property_type.value = asset.property_type || '';
    form.estimated_value.value = asset.estimated_value ?? '';
    form.valuation_date.value = asset.valuation_date || form.valuation_date.value;
    form.acb.value = asset.acb ?? '';
    form.principal_residence.checked = Boolean(asset.principal_residence);
  }
  renderOwnershipFields(ownerFields, assetState.people, asset?.owners || [], updateSaveButton);
  baseline = signature();
  updateSaveButton();
  dialog.hidden = false;
}

export function renderRealEstate(target) {
  const assets = assetState.realEstateAssets;
  const rows = assets.map((asset) => {
    const owners = (asset.owners || []).length
      ? asset.owners.map((owner) => `${owner.name} (${(Number(owner.share) * 100).toFixed(0)}%)`).join(', ')
      : 'Unassigned';
    return `<tr class="real-estate-primary-row"><td>${asset.name}</td><td>${asset.property_type || ''}</td><td>${money(asset.estimated_value, true)}</td><td>${money(asset.acb, true)}</td><td></td><td>${asset.principal_residence ? 'Yes' : 'No'}</td><td>${asset.valuation_date}</td><td><button class="table-action" type="button" data-edit-real-estate="${asset.id}">Edit</button></td></tr><tr class="real-estate-owner-row"><td></td><td colspan="7"><strong>Owners:</strong> ${owners}</td></tr>`;
  }).join('');
  const total = assets.reduce((sum, asset) => sum + Number(asset.estimated_value || 0), 0);
  target.innerHTML = `<section class="asset-section"><div class="section-heading"><div><h2>Real estate</h2><p class="section-total">${assets.length} asset${assets.length === 1 ? '' : 's'} · current estimated value ${money(total)}</p></div><button class="view-action section-add-account" type="button" data-add-real-estate>+ Add</button></div>${assets.length ? `<div class="table-card"><table class="real-estate-table"><thead><tr><th>Asset</th><th>Type</th><th>Estimated value</th><th>ACB</th><th>Ownership</th><th>Principal residence</th><th>As of</th><th></th></tr></thead><tbody>${rows}</tbody><tfoot><tr class="total-row"><th colspan="2">Total current value</th><th>${money(total)}</th><th colspan="5"></th></tr></tfoot></table></div>` : '<div class="empty-panel"><p>No real-estate assets yet.</p></div>'}</section>`;
  target.querySelector('[data-add-real-estate]')?.addEventListener('click', () => openRealEstateDialog());
  target.querySelectorAll('[data-edit-real-estate]').forEach((button) => {
    button.addEventListener('click', () => openRealEstateDialog(Number(button.dataset.editRealEstate)));
  });
}

export function initializeRealEstate(onSaved) {
  saved = onSaved;
  document.querySelector('#close-real-estate-dialog').addEventListener('click', () => { dialog.hidden = true; });
  form.addEventListener('input', updateSaveButton);
  form.addEventListener('change', updateSaveButton);
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(form));
    const existing = assetState.realEstateAssets.find((item) => item.id === editingId);
    const payload = {
      ...values,
      owners: selectedOwners(ownerFields),
      effective_tax_rate: existing?.effective_tax_rate ?? null,
      principal_residence: form.principal_residence.checked,
    };
    saveButton.disabled = true;
    try {
      await saveJson(
        editingId ? `/api/model/real-estate/${editingId}` : '/api/model/real-estate',
        editingId ? 'PUT' : 'POST',
        payload,
      );
      dialog.hidden = true;
      await saved();
    } catch (error) {
      showError(message, error);
      saveButton.disabled = false;
    }
  });
}
