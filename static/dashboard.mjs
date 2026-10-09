// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {accountTypeLabel} from './account-types.mjs';
import {escapeHtml, htmlWithLanguageSpans, sourceTextSpan} from './html.mjs';
import {t, locale} from './i18n.mjs';

const money = (value) => Number(value || 0).toLocaleString(locale, {minimumFractionDigits: 2, maximumFractionDigits: 2});
async function loadDashboard() {
  const response = await fetch('/api/dashboard');
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.error || `${response.status}`);
    error.language = 'en-CA';
    throw error;
  }
  const preferredLiquidity = data.liquidity_by_type.non_registered;
  const regularMetrics = [
    [t('dashboard.gross'), `$${money(data.gross_assets)}`, t('dashboard.gross_note')],
    [t('dashboard.immovable'), `$${money(data.immovable_value)}`, t('dashboard.immovable_note')],
    [t('dashboard.invested'), `$${money(data.invested_value)}`, t('dashboard.invested_note')],
    [t('dashboard.gics'), `$${money(data.gic_value)}`, t('dashboard.gics_note')],
    [t('dashboard.liquidity'), `$${money(preferredLiquidity)} / $${money(data.liquidity_value)}`, t('dashboard.liquidity_note')],
  ];
  const uninvestedCard = `<a href="/accounts" class="summary-pill summary-pill-alert"><p>${t('dashboard.cash')}</p><strong>$${money(data.uninvested_security_value)}</strong><small>${t('dashboard.cash_note')}</small></a>`;
  const lowRateCard = `<a href="/accounts" class="summary-pill summary-pill-alert"><p>${t('dashboard.savings', {threshold: (data.savings_threshold * 100).toFixed(2)})}</p><strong>$${money(data.low_rate_value)}</strong><small>${t('dashboard.savings_note')}</small></a>`;
  document.querySelector('#dashboard-metrics').innerHTML = regularMetrics.map(([label, value, note]) => `<article class="summary-pill"><p>${label}</p><strong>${value}</strong><small>${note}</small></article>`).join('') + uninvestedCard + lowRateCard;
  document.querySelector('#dashboard-categories').innerHTML = data.categories.map((item) => `<div class="dashboard-line"><span>${escapeHtml(accountTypeLabel(item.type, item.label))} <small>${t(item.count === 1 ? 'dashboard.account' : 'dashboard.accounts', {count: Number(item.count)})}</small></span><strong>$${money(item.total)}</strong></div>`).join('');
  document.querySelector('#dashboard-liquidity').innerHTML = `${Object.entries(data.liquidity_by_type).filter(([type]) => type !== 'rrsp').map(([type, value]) => `<div class="dashboard-line"><span>${escapeHtml(accountTypeLabel(type))}</span><strong>$${money(value)}</strong></div>`).join('')}<div class="dashboard-line"><span>${t('dashboard.rrsp_uninvested')} <small>${t('dashboard.rrsp_note')}</small></span><strong>$${money(data.rrsp_uninvested)}</strong></div>`;
  document.querySelector('#dashboard-maturities').innerHTML = data.maturities.length
    ? data.maturities.sort((a, b) => a.maturity_date.localeCompare(b.maturity_date)).slice(0, 8).map((item) => `<div class="dashboard-line"><span>${escapeHtml(item.institution)} · ${escapeHtml(item.name)}<small>${escapeHtml(item.maturity_date)}</small></span><strong>$${money(item.amount)}</strong></div>`).join('')
    : `<p class="dashboard-empty">${t('dashboard.no_maturities')}</p>`;
  document.querySelector('#dashboard-transactions').innerHTML = data.recent_transactions.length
    ? `<div class="table-card"><table><thead><tr><th>${t('dashboard.date')}</th><th>${t('dashboard.account_header')}</th><th>${t('dashboard.description')}</th><th>${t('dashboard.amount')}</th></tr></thead><tbody>${data.recent_transactions.map((item) => `<tr><td>${escapeHtml(item.transaction_date)}</td><td>${escapeHtml(item.institution || '')} · ${escapeHtml(item.account_number || '')}</td><td>${sourceTextSpan(item.description || '', item.description_language || '')}</td><td>${money(item.amount)}</td></tr>`).join('')}</tbody></table></div>`
    : `<p class="dashboard-empty">${t('dashboard.no_transactions')}</p>`;
}
loadDashboard().catch((error) => {
  const message = error.language === locale
    ? escapeHtml(error.message)
    : htmlWithLanguageSpans(
      ({message}) => t('dashboard.load_error', {message}),
      {message: error.message},
    );
  document.querySelector('#dashboard-metrics').innerHTML = `<p class="form-message error">${message}</p>`;
});
