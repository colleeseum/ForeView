const tabs = document.querySelectorAll('.view-tab');
const dialog = document.querySelector('#account-dialog');
const dialogForm = document.querySelector('#account-dialog-form');
const dialogTitle = document.querySelector('#account-dialog-title');
const dialogMessage = document.querySelector('#account-dialog-message');
const ownerFields = document.querySelector('#dialog-owner-fields');
const subaccountDialog = document.querySelector('#subaccount-dialog');
const subaccountForm = document.querySelector('#subaccount-dialog-form');
const subaccountTitle = document.querySelector('#subaccount-dialog-title');
const subaccountMessage = document.querySelector('#subaccount-dialog-message');
const subaccountParent = document.querySelector('#subaccount-parent');
const realEstateDialog = document.querySelector('#real-estate-dialog');
const realEstateForm = document.querySelector('#real-estate-dialog-form');
const realEstateTitle = document.querySelector('#real-estate-dialog-title');
const realEstateMessage = document.querySelector('#real-estate-dialog-message');
const realEstateOwnerFields = document.querySelector('#real-estate-owner-fields');
const realEstateOwnerTotal = document.querySelector('#real-estate-owner-total');
const realEstateSaveButton = realEstateForm.querySelector('button[type="submit"]');
let people = [];
let accounts = [];
let categoryTotals = [];
let holdings = [];
let realEstateAssets = [];
let editingId = null;
let editingRealEstateId = null;
let realEstateBaseline = '';
let dialogBaseline = '';
const assetParams = new URLSearchParams(window.location.search);
const validAssetViews = ['non_registered', 'tfsa', 'rrsp', 'real_estate'];
let assetView = validAssetViews.includes(assetParams.get('tab')) ? assetParams.get('tab') : 'non_registered';

function syncAssetLocation() {
  const params = new URLSearchParams(window.location.search);
  if (assetView === 'summary') params.delete('tab');
  else params.set('tab', assetView);
  const query = params.toString();
  window.history.replaceState({}, '', `${window.location.pathname}${query ? `?${query}` : ''}`);
}

function activateAssetTab() {
  tabs.forEach((item) => {
    const view = item.dataset.view === 'accounts-summary' ? 'summary' : item.dataset.view;
    item.classList.toggle('active', view === assetView);
  });
  const panelId = assetView === 'summary' ? 'accounts-summary' : 'accounts-table';
  document.querySelectorAll('.view-panel').forEach((panel) => panel.classList.toggle('active', panel.id === panelId));
}

tabs.forEach((tab) => tab.addEventListener('click', () => {
  assetView = tab.dataset.view === 'accounts-summary' ? 'summary' : tab.dataset.view;
  syncAssetLocation();
  activateAssetTab();
  renderAccounts();
}));

syncAssetLocation();
activateAssetTab();

const assetGroups = [
  ['non_registered', 'Non-registered'],
  ['tfsa', 'TFSA'],
  ['rrsp', 'RRSP'],
];
const securityInstitutions = new Set(['questrade', 'sunlife', 'sun life', 'manulife']);

function isSecurityAccount(account) {
  return account?.asset_kind !== 'gic' && securityInstitutions.has(String(account?.institution || '').trim().toLowerCase());
}

function renderSummary() {
  const totals = assetGroups.map(([type, label]) => {
    const serverTotal = categoryTotals.find((item) => item.type === type);
    return {label, total: Number(serverTotal?.total || 0), count: Number(serverTotal?.count || 0)};
  });
  const grandTotal = totals.reduce((sum, item) => sum + item.total, 0);
  document.querySelector('#asset-summary-content').innerHTML = `<div class="summary-pill-grid">${totals.map((item) => `<article class="summary-pill"><p>${item.label}</p><strong>${item.total.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</strong><small>${item.count} account${item.count === 1 ? '' : 's'}</small></article>`).join('')}<article class="summary-pill summary-pill-total"><p>Total assets</p><strong>${grandTotal.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</strong></article></div>`;
}

async function loadAccounts() {
  const response = await fetch('/api/model/accounts');
  ({ accounts, category_totals: categoryTotals } = await response.json());
  const holdingsResponse = await fetch('/api/model/holdings');
  ({ holdings } = await holdingsResponse.json());
  const realEstateResponse = await fetch('/api/model/real-estate');
  ({ assets: realEstateAssets } = await realEstateResponse.json());
  renderAccounts();
}

function renderRealEstate() {
  const target = document.querySelector('#accounts-table-content');
  const money = (value) => value == null ? '' : Number(value).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
  const rows = realEstateAssets.map((asset) => {
    const owners = (asset.owners || []).length ? asset.owners.map((owner) => `${owner.name} (${(Number(owner.share) * 100).toFixed(0)}%)`).join(', ') : 'Unassigned';
    return `<tr class="real-estate-primary-row"><td>${asset.name}</td><td>${asset.property_type || ''}</td><td>${money(asset.estimated_value)}</td><td>${money(asset.acb)}</td><td></td><td>${asset.principal_residence ? 'Yes' : 'No'}</td><td>${asset.valuation_date}</td><td><button class="table-action" type="button" data-edit-real-estate="${asset.id}">Edit</button></td></tr><tr class="real-estate-owner-row"><td></td><td colspan="7"><strong>Owners:</strong> ${owners}</td></tr>`;
  }).join('');
  const total = realEstateAssets.reduce((sum, asset) => sum + Number(asset.estimated_value || 0), 0);
  target.innerHTML = `<section class="asset-section"><div class="section-heading"><div><h2>Real estate</h2><p class="section-total">${realEstateAssets.length} asset${realEstateAssets.length === 1 ? '' : 's'} · current estimated value ${money(total)}</p></div><button class="view-action section-add-account" type="button" data-add-real-estate>+ Add</button></div>${realEstateAssets.length ? `<div class="table-card"><table class="real-estate-table"><thead><tr><th>Asset</th><th>Type</th><th>Estimated value</th><th>ACB</th><th>Ownership</th><th>Principal residence</th><th>As of</th><th></th></tr></thead><tbody>${rows}</tbody><tfoot><tr class="total-row"><th colspan="2">Total current value</th><th>${money(total)}</th><th colspan="5"></th></tr></tfoot></table></div>` : '<div class="empty-panel"><p>No real-estate assets yet.</p></div>'}</section>`;
  target.querySelector('[data-add-real-estate]')?.addEventListener('click', () => openRealEstateDialog());
  target.querySelectorAll('[data-edit-real-estate]').forEach((button) => button.addEventListener('click', () => openRealEstateDialog(Number(button.dataset.editRealEstate))));
}

function renderHoldings(accountId) {
  const accountHoldings = holdings.filter((item) => Number(item.account_id) === Number(accountId));
  const account = accounts.find((item) => Number(item.id) === Number(accountId));
  if (!account || (!accountHoldings.length && !isSecurityAccount(account))) return '';
  const total = accountHoldings.reduce((sum, item) => sum + Number(item.market_value || 0), 0);
  const money = (value) => Number(value || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
  const rows = accountHoldings.map((item) => `<tr><td>${item.fund_code} ${item.fund_name}</td><td>${item.asset_class || ''}</td><td>${Number(item.units).toLocaleString(undefined, {minimumFractionDigits: 3, maximumFractionDigits: 5})}</td><td>${money(item.unit_price)}</td><td>${money(item.market_value)}</td><td>${item.allocation_pct == null ? '' : `${Number(item.allocation_pct).toFixed(1)}%`}</td><td>${item.valuation_date}</td></tr>`).join('');
  const accountTotal = account?.latest_amount == null ? null : Number(account.latest_amount);
  const cash = accountTotal == null ? null : Math.max(0, accountTotal - total);
  const summary = `${account?.institution || ''} · ${account?.account_number || ''} · ${accountHoldings.length} securities · securities ${money(total)}${accountTotal == null ? '' : ` · cash ${money(cash)} · account total ${money(accountTotal)}`}`;
  const valuationDate = accountHoldings[0]?.valuation_date || account.latest_date || '';
  const cashRow = cash == null ? '' : `<tr class="portfolio-cash-row"><td colspan="4">Cash not invested</td><td>${money(cash)}</td><td></td><td>${valuationDate}</td></tr>`;
  const completeTotal = accountTotal == null ? total : accountTotal;
  return `<section id="portfolio-${accountId}" class="asset-section portfolio-section" hidden><div class="section-heading"><div><h2>Portfolio</h2><p class="section-total">${summary}</p></div></div><div class="table-card"><table><thead><tr><th>Fund</th><th>Asset class</th><th>Units</th><th>Unit price</th><th>Market value</th><th>Allocation</th><th>As of</th></tr></thead><tbody>${rows}${cashRow}</tbody><tfoot><tr><th colspan="4">Securities total</th><th>${money(total)}</th><th colspan="2"></th></tr><tr class="total-row"><th colspan="4">Total account value</th><th>${money(completeTotal)}</th><th colspan="2"></th></tr></tfoot></table></div></section>`;
}

function renderAccounts() {
  if (assetView === 'real_estate') {
    renderRealEstate();
    return;
  }
  if (assetView === 'summary') {
    renderSummary();
    document.querySelector('#accounts-table-content').replaceChildren();
    return;
  }
  const target = document.querySelector('#accounts-table-content');
  if (!accounts.length) { target.textContent = 'No accounts yet. Use + Add to create one.'; return; }
  const groups = assetGroups.filter(([type]) => type === assetView);
  target.innerHTML = groups.map(([type, label]) => {
    const items = accounts.filter((account) => account.account_type === type);
    const orderedItems = items.filter((account) => !account.parent_account_id).flatMap((parent) => [
      parent,
      ...items.filter((child) => child.parent_account_id === parent.id),
    ]);
    const categoryTotal = categoryTotals.find((item) => item.type === type);
    const totalItems = items.filter((account) => !account.parent_account_id);
    const childCount = Number(categoryTotal?.gic_count || 0);
    const total = Number(categoryTotal?.total || 0);
    const totalText = total.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
    const hasMaturity = orderedItems.some((account) => account.maturity_date);
    const hasNotInvested = orderedItems.some((account) => isSecurityAccount(account));
    const tableColumns = [18, 11, ...(hasMaturity ? [13] : []), 14, ...(hasNotInvested ? [10] : []), 6, 6, 23];
    const columnTotal = tableColumns.reduce((sum, width) => sum + width, 0);
    const colgroup = `<colgroup>${tableColumns.map((width) => `<col style="width:${(width / columnTotal * 100).toFixed(2)}%">`).join('')}</colgroup>`;
    const table = (rows) => `<div class="table-card"><table>${colgroup}<thead><tr><th>Account</th><th>Name</th>${hasMaturity ? '<th>Maturity date</th>' : ''}<th>Latest balance</th>${hasNotInvested ? '<th>Not invested</th>' : ''}<th>Rate</th><th class="compact-header"><span class="column-help" title="Redeemable before maturity" aria-label="Redeemable before maturity">🔒</span></th><th></th></tr></thead><tbody>${rows.map((account) => {
      const accountHoldings = holdings.filter((item) => Number(item.account_id) === account.id);
      const securitiesValue = accountHoldings.reduce((sum, item) => sum + Number(item.market_value || 0), 0);
      const notInvested = isSecurityAccount(account) && account.latest_amount != null
        ? Math.max(0, Number(account.latest_amount) - securitiesValue)
        : null;
      const notInvestedCell = notInvested == null ? '' : `<span class="attention-value">${notInvested.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>`;
      const displayedBalance = account.parent_account_id ? account.latest_amount : account.rollup_amount;
      const row = `<tr class="${account.asset_kind === 'gic' ? 'subaccount-row' : 'parent-row'}">${account.asset_kind === 'gic' ? `<td colspan="2"><span class="tree-branch">└─</span>${account.name || ''}</td>` : `<td>${account.institution || ''} · ${account.account_number || ''}</td><td>${account.name || ''}</td>`}${hasMaturity ? `<td>${account.maturity_date || ''}</td>` : ''}<td>${displayedBalance == null ? '' : Number(displayedBalance).toLocaleString()}</td>${hasNotInvested ? `<td>${notInvestedCell}</td>` : ''}<td>${account.interest_rate == null ? '' : `${(Number(account.interest_rate) * 100).toFixed(2)}%`}</td><td>${account.asset_kind === 'gic' ? (account.redeemable ? 'Yes' : 'No') : ''}</td><td><button class="table-action" type="button" data-edit-account="${account.id}">Edit</button>${account.asset_kind !== 'gic' ? ` <button class="table-action" type="button" data-add-subaccount="${account.id}">Add subaccount</button>` : ''}${isSecurityAccount(account) ? ` <button class="table-action" type="button" data-toggle-portfolio="${account.id}">Portfolio</button>` : ''}</td></tr>`;
      const hasGicChildren = account.asset_kind !== 'gic' && items.some((child) => child.parent_account_id === account.id && child.asset_kind === 'gic');
      if (!hasGicChildren) return row;
      const nonGicBalance = Number(account.non_gic_amount || 0).toLocaleString();
      const componentRow = `<tr class="subaccount-row account-balance-row"><td colspan="2"><span class="tree-branch">└─</span>Non-GIC balance</td>${hasMaturity ? '<td></td>' : ''}<td>${nonGicBalance}</td>${hasNotInvested ? '<td></td>' : ''}<td></td><td></td><td></td></tr>`;
      return `${row}${componentRow}`;
    }).join('')}</tbody><tfoot><tr class="total-row"><th colspan="${2 + (hasMaturity ? 1 : 0)}">Total</th><th>${totalText}</th>${hasNotInvested ? '<th></th>' : ''}<th colspan="3"></th></tr></tfoot></table></div>`;
    const accountCount = Number(categoryTotal?.count || 0);
    const countText = `${accountCount} account${accountCount === 1 ? '' : 's'}${childCount ? ` · ${childCount} GIC${childCount === 1 ? '' : 's'}` : ''}`;
    return `<section class="asset-section"><div class="section-heading"><div><h2>${label}</h2><p class="section-total">${countText} · subtotal ${totalText}</p></div><button class="view-action section-add-account" type="button" data-add-account-type="${type}">+ Add</button></div>${items.length ? table(orderedItems) : '<div class="empty-panel"><p>No accounts in this category.</p></div>'}</section>${items.filter((item) => isSecurityAccount(item)).map((item) => renderHoldings(item.id)).join('')}`;
  }).join('');
  target.querySelectorAll('[data-edit-account]').forEach((button) => button.addEventListener('click', () => {
    const account = accounts.find((item) => item.id === Number(button.dataset.editAccount));
    if (account && account.asset_kind === 'gic') openSubaccountDialog(account.id);
    else openDialog(Number(button.dataset.editAccount));
  }));
  target.querySelectorAll('[data-add-subaccount]').forEach((button) => button.addEventListener('click', () => openSubaccountDialog(null, Number(button.dataset.addSubaccount))));
  target.querySelectorAll('[data-add-account-type]').forEach((button) => button.addEventListener('click', () => openDialog(null, button.dataset.addAccountType)));
  target.querySelectorAll('[data-toggle-portfolio]').forEach((button) => button.addEventListener('click', () => {
    const portfolio = target.querySelector(`#portfolio-${button.dataset.togglePortfolio}`);
    const visible = portfolio && !portfolio.hidden;
    if (portfolio) portfolio.hidden = visible;
    button.textContent = visible ? 'Portfolio' : 'Hide portfolio';
  }));
}

document.querySelector('#reload-assets')?.addEventListener('click', () => window.location.reload());

function loadSubaccountParents(selectedId = null) {
  subaccountParent.replaceChildren();
  accounts.filter((account) => account.asset_kind !== 'gic').forEach((account) => {
    subaccountParent.add(new Option(`${account.account_number} · ${account.institution || ''} ${account.name || ''}`, account.id, false, account.id === selectedId));
  });
}

async function loadPeople() {
  people = (await (await fetch('/api/model/people')).json()).people;
}

function renderOwnerFields(selected = []) {
  const selectedById = new Map(selected.map((item) => [item.person_id, item.share * 100]));
  ownerFields.replaceChildren(...people.map((person) => {
    const label = document.createElement('label');
    const share = selectedById.get(person.id) || 100;
    label.className = 'owner-field';
    label.innerHTML = `<input type="checkbox" data-person-id="${person.id}" ${selectedById.has(person.id) ? 'checked' : ''}> <span>${person.name}</span><input type="number" data-share-id="${person.id}" value="${share}" min="0.01" max="100" step="0.01">%`;
    label.querySelector('input[type="checkbox"]').addEventListener('change', () => {
      const checked = [...ownerFields.querySelectorAll('input[type="checkbox"]:checked')];
      if (checked.length === 2 && checked.every((item) => Number(ownerFields.querySelector(`[data-share-id="${item.dataset.personId}"]`).value) === 100)) {
        checked.forEach((item) => { ownerFields.querySelector(`[data-share-id="${item.dataset.personId}"]`).value = 50; });
      } else if (checked.length === 1) {
        const share = ownerFields.querySelector(`[data-share-id="${checked[0].dataset.personId}"]`);
        if (Number(share.value) === 50) share.value = 100;
      }
    });
    return label;
  }));
}

function ownerDetails(account) {
  if (!account.owner_details) return [];
  return account.owner_details.split(',').map((item) => {
    const [personId, share] = item.split(':');
    return {person_id: Number(personId), share: Number(share)};
  });
}

function dialogSignature() {
  const fields = [...dialogForm.elements].filter((field) => field.name).map((field) => `${field.name}:${field.type === 'checkbox' ? field.checked : field.value}`);
  const owners = [...ownerFields.querySelectorAll('input[type="checkbox"]')].map((field) => `${field.dataset.personId}:${field.checked}:${ownerFields.querySelector(`[data-share-id="${field.dataset.personId}"]`).value}`);
  return [...fields, ...owners].join('|');
}

function updateDialogSaveButton() {
  dialogForm.querySelector('button[type="submit"], button:not([type])').disabled = dialogSignature() === dialogBaseline;
}

function openDialog(accountId = null, category = 'non_registered') {
  editingId = accountId;
  const account = accounts.find((item) => item.id === accountId);
  dialogTitle.textContent = account ? 'Edit account' : 'Add account';
  dialogMessage.textContent = '';
  dialogForm.reset();
  dialogForm.balance_date.value = new Date().toISOString().slice(0, 10);
  dialogForm.category.value = category;
  if (account) {
    dialogForm.account_number.value = account.account_number || '';
    dialogForm.institution.value = account.institution || '';
    dialogForm.name.value = account.name || '';
    dialogForm.category.value = account.account_type;
    dialogForm.balance_date.value = account.latest_date || dialogForm.balance_date.value;
    dialogForm.balance_amount.value = account.latest_amount == null ? '' : account.latest_amount;
    dialogForm.interest_rate.value = account.interest_rate == null ? '' : (Number(account.interest_rate) * 100).toFixed(2);
    renderOwnerFields(ownerDetails(account));
  } else renderOwnerFields();
  dialogBaseline = dialogSignature();
  updateDialogSaveButton();
  dialog.hidden = false;
}

function openSubaccountDialog(accountId = null, parentId = null) {
  const account = accounts.find((item) => item.id === accountId);
  subaccountTitle.textContent = account ? 'Edit GIC' : 'Add GIC';
  subaccountMessage.textContent = '';
  subaccountMessage.classList.remove('error');
  subaccountForm.querySelector('button[type="submit"]').disabled = false;
  subaccountForm.reset();
  loadSubaccountParents(account ? account.parent_account_id : parentId);
  subaccountForm.balance_date.value = new Date().toISOString().slice(0, 10);
  if (account) {
    subaccountForm.parent_account_id.value = account.parent_account_id;
    subaccountForm.account_number.value = account.account_number || '';
    subaccountForm.name.value = account.name || '';
    subaccountForm.start_date.value = account.start_date || '';
    subaccountForm.maturity_date.value = account.maturity_date || '';
    subaccountForm.principal.value = account.principal == null ? '' : account.principal;
    subaccountForm.maturity_value.value = account.maturity_value == null ? '' : account.maturity_value;
    subaccountForm.redeemable.checked = Boolean(account.redeemable);
    subaccountForm.balance_date.value = account.latest_date || subaccountForm.balance_date.value;
    subaccountForm.balance_amount.value = account.latest_amount == null ? '' : account.latest_amount;
    subaccountForm.interest_rate.value = account.interest_rate == null ? '' : (Number(account.interest_rate) * 100).toFixed(2);
  }
  subaccountForm.dataset.editingId = accountId || '';
  subaccountDialog.hidden = false;
}

document.querySelector('#close-account-dialog').addEventListener('click', () => { dialog.hidden = true; });
document.querySelector('#close-subaccount-dialog').addEventListener('click', () => { subaccountDialog.hidden = true; });
dialogForm.addEventListener('input', updateDialogSaveButton);
dialogForm.addEventListener('change', updateDialogSaveButton);
dialogForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const saveButton = dialogForm.querySelector('button[type="submit"], button:not([type])');
  saveButton.disabled = true;
  const form = Object.fromEntries(new FormData(dialogForm));
  const owners = [...ownerFields.querySelectorAll('input[type="checkbox"]:checked')].map((check) => ({person_id: Number(check.dataset.personId), share: Number(ownerFields.querySelector(`[data-share-id="${check.dataset.personId}"]`).value) / 100}));
  try {
    const method = editingId ? 'PUT' : 'POST';
    const url = editingId ? `/api/model/accounts/${editingId}` : '/api/model/accounts';
    const payload = editingId ? {...form, owners} : {...form, owners, asset_kind: 'account'};
    const response = await fetch(url, {method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    dialog.hidden = true;
    await loadAccounts();
  } catch (error) { dialogMessage.textContent = error.message; dialogMessage.classList.add('error'); updateDialogSaveButton(); }
});

subaccountForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const saveButton = subaccountForm.querySelector('button[type="submit"]');
  saveButton.disabled = true;
  const form = Object.fromEntries(new FormData(subaccountForm));
  form.asset_kind = 'gic';
  form.redeemable = subaccountForm.redeemable.checked;
  const parent = accounts.find((item) => item.id === Number(form.parent_account_id));
  form.category = parent.account_type;
  form.institution = parent.institution;
  try {
    const editingId = Number(subaccountForm.dataset.editingId || 0);
    const response = await fetch(editingId ? `/api/model/accounts/${editingId}` : '/api/model/accounts', {
      method: editingId ? 'PUT' : 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(form),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    subaccountDialog.hidden = true;
    await loadAccounts();
  } catch (error) {
    subaccountMessage.textContent = error.message;
    subaccountMessage.classList.add('error');
    saveButton.disabled = false;
  }
});

Promise.all([loadPeople(), loadAccounts()]);
