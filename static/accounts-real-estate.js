document.querySelector('#close-real-estate-dialog').addEventListener('click', () => { realEstateDialog.hidden = true; });

function openRealEstateDialog(assetId = null) {
  editingRealEstateId = assetId;
  const asset = realEstateAssets.find((item) => item.id === assetId);
  realEstateTitle.textContent = asset ? 'Edit real-estate asset' : 'Add real-estate asset';
  realEstateMessage.textContent = '';
  realEstateMessage.classList.remove('error');
  realEstateForm.reset();
  realEstateForm.valuation_date.value = new Date().toISOString().slice(0, 10);
  if (asset) {
    realEstateForm.name.value = asset.name || '';
    realEstateForm.property_type.value = asset.property_type || '';
    realEstateForm.estimated_value.value = asset.estimated_value ?? '';
    realEstateForm.valuation_date.value = asset.valuation_date || realEstateForm.valuation_date.value;
    realEstateForm.acb.value = asset.acb ?? '';
    realEstateForm.principal_residence.checked = Boolean(asset.principal_residence);
  }
  renderRealEstateOwnerFields(asset?.owners || []);
  realEstateBaseline = realEstateSignature();
  updateRealEstateSaveButton();
  realEstateDialog.hidden = false;
}

function renderRealEstateOwnerFields(selected = []) {
  const selectedById = new Map(selected.map((item) => [item.person_id, Number(item.share) * 100]));
  realEstateOwnerFields.replaceChildren(...people.map((person) => {
    const label = document.createElement('label');
    const share = selectedById.get(person.id) || 100;
    label.className = 'owner-field';
    label.innerHTML = `<input type="checkbox" data-real-estate-person-id="${person.id}" ${selectedById.has(person.id) ? 'checked' : ''}> <span>${person.name}</span><input type="number" data-real-estate-share-id="${person.id}" value="${share}" min="0.01" max="100" step="0.01">%`;
    label.querySelector('input[type="checkbox"]').addEventListener('change', () => {
      const checked = [...realEstateOwnerFields.querySelectorAll('input[data-real-estate-person-id]:checked')];
      if (checked.length === 2 && checked.every((item) => Number(realEstateOwnerFields.querySelector(`[data-real-estate-share-id="${item.dataset.realEstatePersonId}"]`).value) === 100)) {
        checked.forEach((item) => { realEstateOwnerFields.querySelector(`[data-real-estate-share-id="${item.dataset.realEstatePersonId}"]`).value = 50; });
      } else if (checked.length === 1) {
        const shareInput = realEstateOwnerFields.querySelector(`[data-real-estate-share-id="${checked[0].dataset.realEstatePersonId}"]`);
        if (Number(shareInput.value) === 50) shareInput.value = 100;
      }
      updateRealEstateOwnerTotal();
    });
    label.querySelector('input[type="number"]').addEventListener('input', updateRealEstateOwnerTotal);
    return label;
  }));
  updateRealEstateOwnerTotal();
}

function updateRealEstateOwnerTotal() {
  const total = [...realEstateOwnerFields.querySelectorAll('input[data-real-estate-person-id]:checked')]
    .reduce((sum, check) => sum + Number(realEstateOwnerFields.querySelector(`[data-real-estate-share-id="${check.dataset.realEstatePersonId}"]`).value || 0), 0);
  realEstateOwnerTotal.textContent = `Selected ownership: ${total.toFixed(2)}%${Math.abs(total - 100) < 0.01 ? '' : ' · must equal 100%'}`;
  realEstateOwnerTotal.classList.toggle('error', Math.abs(total - 100) >= 0.01);
  updateRealEstateSaveButton(total);
}

function realEstateSignature() {
  const fields = [...realEstateForm.elements].filter((field) => field.name)
    .map((field) => `${field.name}:${field.type === 'checkbox' ? field.checked : field.value}`);
  const owners = [...realEstateOwnerFields.querySelectorAll('input[data-real-estate-person-id]')]
    .map((field) => `${field.dataset.realEstatePersonId}:${field.checked}:${realEstateOwnerFields.querySelector(`[data-real-estate-share-id="${field.dataset.realEstatePersonId}"]`).value}`);
  return [...fields, ...owners].join('|');
}

function updateRealEstateSaveButton(total = null) {
  const selectedTotal = total == null
    ? [...realEstateOwnerFields.querySelectorAll('input[data-real-estate-person-id]:checked')]
      .reduce((sum, check) => sum + Number(realEstateOwnerFields.querySelector(`[data-real-estate-share-id="${check.dataset.realEstatePersonId}"]`).value || 0), 0)
    : total;
  realEstateSaveButton.disabled = realEstateSignature() === realEstateBaseline || Math.abs(selectedTotal - 100) >= 0.01;
}

realEstateForm.addEventListener('input', updateRealEstateSaveButton);
realEstateForm.addEventListener('change', updateRealEstateSaveButton);

realEstateForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = Object.fromEntries(new FormData(realEstateForm));
  const existingAsset = realEstateAssets.find((item) => item.id === editingRealEstateId);
  const owners = [...realEstateOwnerFields.querySelectorAll('input[data-real-estate-person-id]:checked')].map((check) => ({person_id: Number(check.dataset.realEstatePersonId), share: Number(realEstateOwnerFields.querySelector(`[data-real-estate-share-id="${check.dataset.realEstatePersonId}"]`).value) / 100}));
  const payload = {
    ...form,
    owners,
    effective_tax_rate: existingAsset?.effective_tax_rate ?? null,
    principal_residence: realEstateForm.principal_residence.checked,
  };
  realEstateSaveButton.disabled = true;
  try {
    const method = editingRealEstateId ? 'PUT' : 'POST';
    const url = editingRealEstateId ? `/api/model/real-estate/${editingRealEstateId}` : '/api/model/real-estate';
    const response = await fetch(url, {method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    realEstateDialog.hidden = true;
    await loadAccounts();
  } catch (error) {
    realEstateMessage.textContent = error.message;
    realEstateMessage.classList.add('error');
    realEstateSaveButton.disabled = false;
  }
});
