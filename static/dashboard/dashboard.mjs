// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {accountTypeLabel} from '../shared/account-types.mjs';
import {escapeHtml, htmlWithLanguageSpans, sourceTextSpan} from '../shared/html.mjs';
import {t, locale} from '../shared/i18n.mjs';
import {formatDate, formatMoneyCents, formatNumber} from '../shared/locale-format.mjs';

function money(value) {
  if (value === null || value === undefined) return t('dashboard.unavailable');
  const amount = value;
  // The compatibility API returns dollar floats. Below 2**44 their rounding error
  // is less than half a cent; above it, refuse to infer authoritative cents.
  if (typeof amount !== 'number' || !Number.isFinite(amount) || Math.abs(amount) >= 2 ** 44) {
    const error = new RangeError(t('dashboard.money_precision_error'));
    error.language = locale;
    throw error;
  }
  return formatMoneyCents(BigInt(amount.toFixed(2).replace('.', '')));
}
function displayStoredDate(value) {
  try {
    return formatDate(value);
  } catch (error) {
    if (error instanceof TypeError || error instanceof RangeError) return String(value ?? '');
    throw error;
  }
}
async function loadDashboard() {
  const response = await fetch('/api/dashboard');
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.error || `${response.status}`);
    error.language = 'en-CA';
    throw error;
  }
  // Validate every displayed amount before writing any financial panel, so a
  // later unsafe category, maturity, or transaction cannot leave partial results.
  [
    data.gross_assets, data.immovable_value, data.invested_value, data.gic_value,
    data.liquidity_value, data.rrsp_uninvested, data.uninvested_security_value,
    data.low_rate_value, ...Object.values(data.liquidity_by_type),
    ...data.categories.map((item) => item.total),
    ...data.maturities.map((item) => item.amount),
    ...data.recent_transactions.map((item) => item.amount),
  ].forEach(money);
  const preferredLiquidity = data.liquidity_by_type.non_registered;
  const regularMetrics = [
    [t('dashboard.gross'), money(data.gross_assets), t('dashboard.gross_note')],
    [t('dashboard.immovable'), money(data.immovable_value), t('dashboard.immovable_note')],
    [t('dashboard.invested'), money(data.invested_value), t('dashboard.invested_note')],
    [t('dashboard.gics'), money(data.gic_value), t('dashboard.gics_note')],
    [t('dashboard.liquidity'), `${money(preferredLiquidity)} / ${money(data.liquidity_value)}`, t('dashboard.liquidity_note')],
  ];
  const uninvestedCard = `<a href="/accounts" class="summary-pill summary-pill-alert"><p>${t('dashboard.cash')}</p><strong>${money(data.uninvested_security_value)}</strong><small>${t('dashboard.cash_note')}</small></a>`;
  const lowRateCard = `<a href="/accounts" class="summary-pill summary-pill-alert"><p>${t('dashboard.savings', {threshold: formatNumber(data.savings_threshold * 100, {minimumFractionDigits: 2, maximumFractionDigits: 2})})}</p><strong>${money(data.low_rate_value)}</strong><small>${t('dashboard.savings_note')}</small></a>`;
  document.querySelector('#dashboard-metrics').innerHTML = regularMetrics.map(([label, value, note]) => `<article class="summary-pill"><p>${label}</p><strong>${value}</strong><small>${note}</small></article>`).join('') + uninvestedCard + lowRateCard;
  document.querySelector('#dashboard-categories').innerHTML = data.categories.length ? data.categories.map((item) => `<div class="dashboard-line"><span>${escapeHtml(accountTypeLabel(item.type, item.label))} <small>${t(item.count === 1 ? 'dashboard.account' : 'dashboard.accounts', {count: Number(item.count)})}</small></span><strong>${money(item.total)}</strong></div>`).join('') : `<p class="dashboard-empty">${t('dashboard.no_accounts')}</p>`;
  document.querySelector('#dashboard-liquidity').innerHTML = `${Object.entries(data.liquidity_by_type).filter(([type]) => type !== 'rrsp').map(([type, value]) => `<div class="dashboard-line"><span>${escapeHtml(accountTypeLabel(type))}</span><strong>${money(value)}</strong></div>`).join('')}<div class="dashboard-line"><span>${t('dashboard.rrsp_uninvested')} <small>${t('dashboard.rrsp_note')}</small></span><strong>${money(data.rrsp_uninvested)}</strong></div>`;
  document.querySelector('#dashboard-maturities').innerHTML = data.maturities.length
    ? [...data.maturities].sort((a, b) => a.maturity_date.localeCompare(b.maturity_date)).slice(0, 8).map((item) => `<div class="dashboard-line"><span>${escapeHtml(item.institution)} · ${escapeHtml(item.name)}<small>${escapeHtml(displayStoredDate(item.maturity_date))}</small></span><strong>${money(item.amount)}</strong></div>`).join('')
    : `<p class="dashboard-empty">${t('dashboard.no_maturities')}</p>`;
  document.querySelector('#dashboard-transactions').innerHTML = data.recent_transactions.length
    ? `<p class="fv-help">${t('dashboard.scroll_hint')}</p><div class="fv-table-scroll" tabindex="0" role="region" aria-label="${escapeHtml(t('dashboard.history'))}"><table class="fv-table"><caption>${t('dashboard.history')}</caption><thead><tr><th scope="col">${t('dashboard.date')}</th><th scope="col">${t('dashboard.account_header')}</th><th scope="col">${t('dashboard.description')}</th><th scope="col" class="fv-number">${t('dashboard.amount')}</th></tr></thead><tbody>${data.recent_transactions.map((item) => `<tr><td>${escapeHtml(displayStoredDate(item.transaction_date))}</td><td>${escapeHtml(item.institution || '')} · ${escapeHtml(item.account_number || '')}</td><td>${sourceTextSpan(item.description || '', item.description_language || '')}</td><td class="fv-number">${money(item.amount)}</td></tr>`).join('')}</tbody></table></div>`
    : `<p class="dashboard-empty">${t('dashboard.no_transactions')}</p>`;
  panels().forEach(panel => panel.setAttribute('aria-busy', 'false'));
}
function panels() {
  return ['metrics', 'categories', 'liquidity', 'maturities', 'transactions'].map(name => document.querySelector(`#dashboard-${name}`));
}
loadDashboard().catch((error) => {
  const message = error.language === locale
    ? escapeHtml(error.message)
    : htmlWithLanguageSpans(
      ({message}) => t('dashboard.load_error', {message}),
      {message: error.message},
    );
  panels().forEach((panel, index) => {
    panel.setAttribute('aria-busy', 'false');
    panel.innerHTML = index === 0
      ? `<p class="form-message error fv-feedback fv-feedback--error" role="alert">${message}</p>`
      : `<p class="dashboard-empty">${t('dashboard.unavailable')}</p>`;
  });
});
