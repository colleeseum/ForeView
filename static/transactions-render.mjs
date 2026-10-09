// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {escapeHtml, sourceTextSpan} from './html.mjs';
import {t, locale} from './i18n.mjs';

const money = (value) => value == null ? '' : Number(value).toLocaleString(locale, {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const reconciliationStatuses = new Set([
  'reconciled',
  'no_matching_transactions',
  'difference',
  'needs_review',
  'superseded',
]);

const cashFlowCategories = new Set([
  'contribution',
  'deposit',
  'dividend',
  'grant',
  'growth',
  'interest',
  'other',
  'transfer',
  'withdrawal',
]);

export function cashFlowCategoryLabel(category) {
  const normalized = String(category || '').trim().toLocaleLowerCase();
  return cashFlowCategories.has(normalized)
    ? t(`transactions_render.cash_flow_categories.${normalized}`)
    : category;
}

export function reconciliationStatusLabel(status) {
  return reconciliationStatuses.has(status)
    ? t(`transactions_render.reconciliation_status.${status}`)
    : status;
}

function transactionAccountLabel(item) {
  if (item.asset_kind === 'gic') {
    const parent = [item.parent_institution, item.parent_account_number].filter(Boolean).join(' · ');
    return `${t('accounts.gic')} · ${escapeHtml(parent)}${item.account_name ? ` · ${escapeHtml(item.account_name)}` : ''}`;
  }
  const account = [item.institution, item.account_number].filter(Boolean).join(' · ');
  return `${t('accounts.cash')} · ${escapeHtml(account || item.account_name || '')}`;
}

export function transactionsTableHtml(transactions, openingBalances, accountFiltered) {
  const rows = [...transactions, ...openingBalances].sort((left, right) => {
    const dateOrder = String(right.transaction_date).localeCompare(String(left.transaction_date));
    if (dateOrder) return dateOrder;
    return Number(Boolean(left.is_opening_balance)) - Number(Boolean(right.is_opening_balance));
  });
  if (!rows.length) {
    return `<div class="empty-panel"><h2>${t('transactions_render.none')}</h2><p>${t('transactions_render.import_hint')}</p></div>`;
  }
  const balanceValue = (item, key) => {
    const value = item[key];
    return value == null ? '' : money(value);
  };
  const balanceHeaders = accountFiltered ? `<th>${t('transactions_render.balance_after')}</th>` : `<th>${t('transactions_render.account_balance')}</th><th>${t('transactions_render.combined_balance')}</th>`;
  const body = rows.map((item) => {
    const balances = accountFiltered
      ? `<td>${balanceValue(item, 'balance_after')}</td>`
      : `<td>${balanceValue(item, 'balance_after')}</td><td>${balanceValue(item, 'combined_balance_after')}</td>`;
    const amount = item.is_opening_balance ? '' : money(item.amount);
    const category = item.is_opening_balance
      ? t('transactions_render.balance_anchor')
      : cashFlowCategoryLabel(item.category) || t('transactions_render.unclassified');
    const description = sourceTextSpan(item.description, item.description_language || '');
    return `<tr${item.is_opening_balance ? ' class="opening-balance-row"' : ''}><td>${escapeHtml(item.transaction_date)}</td><td>${transactionAccountLabel(item)}</td><td>${description}</td><td>${amount}</td>${balances}<td>${escapeHtml(category)}</td></tr>`;
  }).join('');
  return `<table><thead><tr><th>${t('transactions_render.date')}</th><th>${t('transactions_render.account')}</th><th>${t('transactions_render.description')}</th><th>${t('transactions_render.amount')}</th>${balanceHeaders}<th>${t('transactions_render.cash_flow')}</th></tr></thead><tbody>${body}</tbody></table>`;
}

export function importHistoryHtml(imports) {
  if (!imports.length) return `<p class="field-note history-empty">${t('transactions_render.no_imports')}</p>`;
  const rows = imports.map((item) => {
    const status = item.reconciliation_status
      ? t('transactions_render.reconciliation', {status: reconciliationStatusLabel(item.reconciliation_status)})
      : t('transactions_render.imported');
    return `<tr><td>${escapeHtml(item.imported_at)}</td><td>${escapeHtml(item.filename)}</td><td>${escapeHtml(item.account_number)}</td><td>${Number(item.row_count)}</td><td>${escapeHtml(status)}</td></tr>`;
  }).join('');
  return `<div class="table-card"><table><thead><tr><th>${t('transactions_render.imported')}</th><th>${t('transactions_render.file')}</th><th>${t('transactions_render.account')}</th><th>${t('transactions_render.rows')}</th><th>${t('transactions_render.status')}</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}
