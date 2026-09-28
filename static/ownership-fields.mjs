function shareInput(container, ownerId) {
  return container.querySelector(`[data-owner-share="${ownerId}"]`);
}

function checkedOwners(container) {
  return [...container.querySelectorAll('input[data-owner-id]:checked')];
}

function adjustDefaultShares(container) {
  const checked = checkedOwners(container);
  if (checked.length === 2 && checked.every((item) => Number(shareInput(container, item.dataset.ownerId).value) === 100)) {
    checked.forEach((item) => { shareInput(container, item.dataset.ownerId).value = 50; });
  } else if (checked.length === 1) {
    const input = shareInput(container, checked[0].dataset.ownerId);
    if (Number(input.value) === 50) input.value = 100;
  }
}

export function renderOwnershipFields(container, people, selected = [], onChange = () => {}) {
  const selectedById = new Map(selected.map((item) => [Number(item.person_id), Number(item.share) * 100]));
  container.replaceChildren(...people.map((person) => {
    const label = document.createElement('label');
    const share = selectedById.get(person.id) || 100;
    label.className = 'owner-field';
    label.innerHTML = `<input type="checkbox" data-owner-id="${person.id}" ${selectedById.has(person.id) ? 'checked' : ''}> <span>${person.name}</span><input type="number" data-owner-share="${person.id}" value="${share}" min="0.01" max="100" step="0.01">%`;
    label.querySelector('input[type="checkbox"]').addEventListener('change', () => {
      adjustDefaultShares(container);
      onChange();
    });
    label.querySelector('input[type="number"]').addEventListener('input', onChange);
    return label;
  }));
  onChange();
}

export function selectedOwners(container) {
  return checkedOwners(container).map((field) => ({
    person_id: Number(field.dataset.ownerId),
    share: Number(shareInput(container, field.dataset.ownerId).value) / 100,
  }));
}

export function ownershipTotal(container) {
  return selectedOwners(container).reduce((sum, owner) => sum + owner.share * 100, 0);
}

export function ownershipSignature(container) {
  return [...container.querySelectorAll('input[data-owner-id]')].map((field) => (
    `${field.dataset.ownerId}:${field.checked}:${shareInput(container, field.dataset.ownerId).value}`
  ));
}
