import {isSecurityAccount, money} from './accounts-format.mjs';
import {renderRealEstate} from './accounts-real-estate.mjs';
import {assetGroups, assetState} from './accounts-state.mjs';

function renderHoldings(accountId) {
  const accountHoldings = assetState.holdings.filter((item) => Number(item.account_id) === Number(accountId));
  const account = assetState.accounts.find((item) => Number(item.id) === Number(accountId));
  if (!account || (!accountHoldings.length && !isSecurityAccount(account))) return '';
  const total = accountHoldings.reduce((sum, item) => sum + Number(item.market_value || 0), 0);
  const rows = accountHoldings.map((item) => `<tr><td>${item.fund_code} ${item.fund_name}</td><td>${item.asset_class || ''}</td><td>${Number(item.units).toLocaleString(undefined, {minimumFractionDigits: 3, maximumFractionDigits: 5})}</td><td>${money(item.unit_price)}</td><td>${money(item.market_value)}</td><td>${item.allocation_pct == null ? '' : `${Number(item.allocation_pct).toFixed(1)}%`}</td><td>${item.valuation_date}</td></tr>`).join('');
  const accountTotal = account.latest_amount == null ? null : Number(account.latest_amount);
  const cash = accountTotal == null ? null : Math.max(0, accountTotal - total);
  const summary = `${account.institution || ''} · ${account.account_number || ''} · ${accountHoldings.length} securities · securities ${money(total)}${accountTotal == null ? '' : ` · cash ${money(cash)} · account total ${money(accountTotal)}`}`;
  const valuationDate = accountHoldings[0]?.valuation_date || account.latest_date || '';
  const cashRow = cash == null ? '' : `<tr class="portfolio-cash-row"><td colspan="4">Cash not invested</td><td>${money(cash)}</td><td></td><td>${valuationDate}</td></tr>`;
  const completeTotal = accountTotal == null ? total : accountTotal;
  return `<section id="portfolio-${accountId}" class="asset-section portfolio-section" hidden><div class="section-heading"><div><h2>Portfolio</h2><p class="section-total">${summary}</p></div></div><div class="table-card"><table><thead><tr><th>Fund</th><th>Asset class</th><th>Units</th><th>Unit price</th><th>Market value</th><th>Allocation</th><th>As of</th></tr></thead><tbody>${rows}${cashRow}</tbody><tfoot><tr><th colspan="4">Securities total</th><th>${money(total)}</th><th colspan="2"></th></tr><tr class="total-row"><th colspan="4">Total account value</th><th>${money(completeTotal)}</th><th colspan="2"></th></tr></tfoot></table></div></section>`;
}

function accountRow(account, items, hasMaturity, hasNotInvested) {
  const accountHoldings = assetState.holdings.filter((item) => Number(item.account_id) === account.id);
  const securitiesValue = accountHoldings.reduce((sum, item) => sum + Number(item.market_value || 0), 0);
  const notInvested = isSecurityAccount(account) && account.latest_amount != null
    ? Math.max(0, Number(account.latest_amount) - securitiesValue)
    : null;
  const notInvestedCell = notInvested == null ? '' : `<span class="attention-value">${money(notInvested)}</span>`;
  const displayedBalance = account.parent_account_id ? account.latest_amount : account.rollup_amount;
  const row = `<tr class="${account.asset_kind === 'gic' ? 'subaccount-row' : 'parent-row'}">${account.asset_kind === 'gic' ? `<td colspan="2"><span class="tree-branch">└─</span>${account.name || ''}</td>` : `<td>${account.institution || ''} · ${account.account_number || ''}</td><td>${account.name || ''}</td>`}${hasMaturity ? `<td>${account.maturity_date || ''}</td>` : ''}<td>${displayedBalance == null ? '' : Number(displayedBalance).toLocaleString()}</td>${hasNotInvested ? `<td>${notInvestedCell}</td>` : ''}<td>${account.interest_rate == null ? '' : `${(Number(account.interest_rate) * 100).toFixed(2)}%`}</td><td>${account.asset_kind === 'gic' ? (account.redeemable ? 'Yes' : 'No') : ''}</td><td><button class="table-action" type="button" data-edit-account="${account.id}">Edit</button>${account.asset_kind !== 'gic' ? ` <button class="table-action" type="button" data-add-subaccount="${account.id}">Add subaccount</button>` : ''}${isSecurityAccount(account) ? ` <button class="table-action" type="button" data-toggle-portfolio="${account.id}">Portfolio</button>` : ''}</td></tr>`;
  const hasGicChildren = account.asset_kind !== 'gic'
    && items.some((child) => child.parent_account_id === account.id && child.asset_kind === 'gic');
  if (!hasGicChildren) return row;
  const componentRow = `<tr class="subaccount-row account-balance-row"><td colspan="2"><span class="tree-branch">└─</span>Non-GIC balance</td>${hasMaturity ? '<td></td>' : ''}<td>${Number(account.non_gic_amount || 0).toLocaleString()}</td>${hasNotInvested ? '<td></td>' : ''}<td></td><td></td><td></td></tr>`;
  return `${row}${componentRow}`;
}

function accountTable(items, hasMaturity, hasNotInvested, totalText) {
  const columns = [18, 11, ...(hasMaturity ? [13] : []), 14, ...(hasNotInvested ? [10] : []), 6, 6, 23];
  const width = columns.reduce((sum, value) => sum + value, 0);
  const colgroup = `<colgroup>${columns.map((value) => `<col style="width:${(value / width * 100).toFixed(2)}%">`).join('')}</colgroup>`;
  const rows = items.map((account) => accountRow(account, items, hasMaturity, hasNotInvested)).join('');
  return `<div class="table-card"><table>${colgroup}<thead><tr><th>Account</th><th>Name</th>${hasMaturity ? '<th>Maturity date</th>' : ''}<th>Latest balance</th>${hasNotInvested ? '<th>Not invested</th>' : ''}<th>Rate</th><th class="compact-header"><span class="column-help" title="Redeemable before maturity" aria-label="Redeemable before maturity">🔒</span></th><th></th></tr></thead><tbody>${rows}</tbody><tfoot><tr class="total-row"><th colspan="${2 + (hasMaturity ? 1 : 0)}">Total</th><th>${totalText}</th>${hasNotInvested ? '<th></th>' : ''}<th colspan="3"></th></tr></tfoot></table></div>`;
}

function renderAccountGroups(target) {
  if (!assetState.accounts.length) {
    target.textContent = 'No accounts yet. Use + Add to create one.';
    return;
  }
  target.innerHTML = assetGroups.filter(([type]) => type === assetState.view).map(([type, label]) => {
    const items = assetState.accounts.filter((account) => account.account_type === type);
    const ordered = items.filter((account) => !account.parent_account_id).flatMap((parent) => [
      parent,
      ...items.filter((child) => child.parent_account_id === parent.id),
    ]);
    const totals = assetState.categoryTotals.find((item) => item.type === type);
    const accountCount = Number(totals?.count || 0);
    const childCount = Number(totals?.gic_count || 0);
    const totalText = money(totals?.total || 0);
    const hasMaturity = ordered.some((account) => account.maturity_date);
    const hasNotInvested = ordered.some((account) => isSecurityAccount(account));
    const countText = `${accountCount} account${accountCount === 1 ? '' : 's'}${childCount ? ` · ${childCount} GIC${childCount === 1 ? '' : 's'}` : ''}`;
    const table = items.length
      ? accountTable(ordered, hasMaturity, hasNotInvested, totalText)
      : '<div class="empty-panel"><p>No accounts in this category.</p></div>';
    const portfolios = items.filter(isSecurityAccount).map((item) => renderHoldings(item.id)).join('');
    return `<section class="asset-section"><div class="section-heading"><div><h2>${label}</h2><p class="section-total">${countText} · subtotal ${totalText}</p></div><button class="view-action section-add-account" type="button" data-add-account-type="${type}">+ Add</button></div>${table}</section>${portfolios}`;
  }).join('');
}

export function renderAssets({openAccount, openGic}) {
  const target = document.querySelector('#accounts-table-content');
  if (assetState.view === 'real_estate') {
    renderRealEstate(target);
    return;
  }
  renderAccountGroups(target);
  target.querySelectorAll('[data-edit-account]').forEach((button) => button.addEventListener('click', () => {
    const account = assetState.accounts.find((item) => item.id === Number(button.dataset.editAccount));
    if (account?.asset_kind === 'gic') openGic(account.id);
    else openAccount(Number(button.dataset.editAccount));
  }));
  target.querySelectorAll('[data-add-subaccount]').forEach((button) => {
    button.addEventListener('click', () => openGic(null, Number(button.dataset.addSubaccount)));
  });
  target.querySelectorAll('[data-add-account-type]').forEach((button) => {
    button.addEventListener('click', () => openAccount(null, button.dataset.addAccountType));
  });
  target.querySelectorAll('[data-toggle-portfolio]').forEach((button) => button.addEventListener('click', () => {
    const portfolio = target.querySelector(`#portfolio-${button.dataset.togglePortfolio}`);
    const visible = portfolio && !portfolio.hidden;
    if (portfolio) portfolio.hidden = visible;
    button.textContent = visible ? 'Portfolio' : 'Hide portfolio';
  }));
}
