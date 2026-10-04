// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {escapeHtml} from './html.mjs';

const money = (value) => value == null ? '' : Number(value).toLocaleString(undefined, {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function transactionAccountLabel(item) {
  if (item.asset_kind === 'gic') {
    const parent = [item.parent_institution, item.parent_account_number].filter(Boolean).join(' · ');
    return `GIC · ${escapeHtml(parent)}${item.account_name ? ` · ${escapeHtml(item.account_name)}` : ''}`;
  }
  const account = [item.institution, item.account_number].filter(Boolean).join(' · ');
  return `Cash · ${escapeHtml(account || item.account_name || '')}`;
}

export function transactionsTableHtml(transactions, openingBalances, accountFiltered) {
  const rows = [...transactions, ...openingBalances].sort((left, right) => {
    const dateOrder = String(right.transaction_date).localeCompare(String(left.transaction_date));
    if (dateOrder) return dateOrder;
    return Number(Boolean(left.is_opening_balance)) - Number(Boolean(right.is_opening_balance));
  });
  if (!rows.length) {
    return '<div class="empty-panel"><h2>No transactions yet</h2><p>Use Import to add bank statements.</p></div>';
  }
  const balanceValue = (item, key) => {
    const value = item[key];
    return value == null ? '' : money(value);
  };
  const balanceHeaders = accountFiltered ? '<th>Balance after</th>' : '<th>Account balance</th><th>Combined balance</th>';
  const body = rows.map((item) => {
    const balances = accountFiltered
      ? `<td>${balanceValue(item, 'balance_after')}</td>`
      : `<td>${balanceValue(item, 'balance_after')}</td><td>${balanceValue(item, 'combined_balance_after')}</td>`;
    const amount = item.is_opening_balance ? '' : money(item.amount);
    const category = item.is_opening_balance ? 'Balance anchor' : (item.category || 'Unclassified');
    return `<tr${item.is_opening_balance ? ' class="opening-balance-row"' : ''}><td>${escapeHtml(item.transaction_date)}</td><td>${transactionAccountLabel(item)}</td><td>${escapeHtml(item.description)}</td><td>${amount}</td>${balances}<td>${escapeHtml(category)}</td></tr>`;
  }).join('');
  return `<table><thead><tr><th>Date</th><th>Account</th><th>Description</th><th>Amount</th>${balanceHeaders}<th>Cash-flow category</th></tr></thead><tbody>${body}</tbody></table>`;
}

export function importHistoryHtml(imports) {
  if (!imports.length) return '<p class="field-note history-empty">No imports yet.</p>';
  const rows = imports.map((item) => {
    const status = item.reconciliation_status ? `Reconciliation: ${item.reconciliation_status}` : 'Imported';
    return `<tr><td>${escapeHtml(item.imported_at)}</td><td>${escapeHtml(item.filename)}</td><td>${escapeHtml(item.account_number)}</td><td>${Number(item.row_count)}</td><td>${escapeHtml(status)}</td></tr>`;
  }).join('');
  return `<div class="table-card"><table><thead><tr><th>Imported</th><th>File</th><th>Account</th><th>Rows</th><th>Status</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}
