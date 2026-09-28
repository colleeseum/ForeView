const money = (value) => Number(value || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[character]));

async function loadDashboard() {
  const response = await fetch('/api/dashboard');
  const data = await response.json();
  const preferredLiquidity = data.liquidity_by_type.non_registered;
  const regularMetrics = [
    ['Gross assets', `$${money(data.gross_assets)}`, 'Financial + immovable assets · RRSP before withdrawal tax'],
    ['Immovable assets', `$${money(data.immovable_value)}`, 'Current real-estate estimates'],
    ['Invested value', `$${money(data.invested_value)}`, 'Current securities holdings'],
    ['GICs / term deposits', `$${money(data.gic_value)}`, 'Maturity and access rules apply'],
    ['Liquidity', `$${money(preferredLiquidity)} / $${money(data.liquidity_value)}`, 'Preferred Non-registered / available including TFSA'],
  ];
  const uninvestedCard = `<a href="/accounts" class="summary-pill summary-pill-alert"><p>Cash in security accounts</p><strong>$${money(data.uninvested_security_value)}</strong><small>Not in securities or GICs · review Assets</small></a>`;
  const lowRateCard = `<a href="/accounts" class="summary-pill summary-pill-alert"><p>Savings below ${(data.savings_threshold * 100).toFixed(2)}%</p><strong>$${money(data.low_rate_value)}</strong><small>Review accounts below threshold · review Assets</small></a>`;
  document.querySelector('#dashboard-metrics').innerHTML = regularMetrics.map(([label, value, note]) => `<article class="summary-pill"><p>${label}</p><strong>${value}</strong><small>${note}</small></article>`).join('') + uninvestedCard + lowRateCard;
  document.querySelector('#dashboard-categories').innerHTML = data.categories.map((item) => `<div class="dashboard-line"><span>${item.label} <small>${item.count} account${item.count === 1 ? '' : 's'}</small></span><strong>$${money(item.total)}</strong></div>`).join('');
  const categoryLabels = {non_registered: 'Non-registered', tfsa: 'TFSA', rrsp: 'RRSP'};
  document.querySelector('#dashboard-liquidity').innerHTML = `${Object.entries(data.liquidity_by_type).filter(([type]) => type !== 'rrsp').map(([type, value]) => `<div class="dashboard-line"><span>${categoryLabels[type]}</span><strong>$${money(value)}</strong></div>`).join('')}<div class="dashboard-line"><span>RRSP uninvested <small>Pre-tax and excluded from liquidity</small></span><strong>$${money(data.rrsp_uninvested)}</strong></div>`;
  document.querySelector('#dashboard-maturities').innerHTML = data.maturities.length
    ? data.maturities.sort((a, b) => a.maturity_date.localeCompare(b.maturity_date)).slice(0, 8).map((item) => `<div class="dashboard-line"><span>${escapeHtml(item.institution)} · ${escapeHtml(item.name)}<small>${escapeHtml(item.maturity_date)}</small></span><strong>$${money(item.amount)}</strong></div>`).join('')
    : '<p class="dashboard-empty">No maturity dates recorded.</p>';
  document.querySelector('#dashboard-transactions').innerHTML = data.recent_transactions.length
    ? `<div class="table-card"><table><thead><tr><th>Date</th><th>Account</th><th>Description</th><th>Amount</th></tr></thead><tbody>${data.recent_transactions.map((item) => `<tr><td>${escapeHtml(item.transaction_date)}</td><td>${escapeHtml(item.institution || '')} · ${escapeHtml(item.account_number || '')}</td><td>${escapeHtml(item.description || '')}</td><td>${money(item.amount)}</td></tr>`).join('')}</tbody></table></div>`
    : '<p class="dashboard-empty">No transactions imported.</p>';
}
loadDashboard().catch((error) => { document.querySelector('#dashboard-metrics').innerHTML = `<p class="form-message error">Could not load dashboard: ${escapeHtml(error.message)}</p>`; });
