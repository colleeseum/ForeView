// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {escapeHtml} from '../shared/html.mjs';
import {t} from '../shared/i18n.mjs';
import {formatMoneyDollars, formatPercent} from '../shared/locale-format.mjs';
import {incomeSourceLabel} from '../shared/income-source-label.mjs';
import {iconAction} from '../shared/icon-actions.mjs';

const money = value => formatMoneyDollars(value ?? 0);
const fieldKeys = {raise_rate: 'raise', salary: 'annual_salary', other_income: 'other_income', rrsp_contribution: 'rrsp_cash', rrsp_deduction: 'rrsp_deduction'};

// Millionth-rate storage corresponds to four decimal places in percentage inputs.
export const rateInputValue = value => (Number(value ?? 0) * 100).toFixed(4).replace(/\.?0+$/, '');

export function projectionTable(rows, {editable = false, overrides = [], household = false, expandedRows = new Set()} = {}) {
  if (!rows.length) return `<p class="empty-panel">${t('salary.no_projection')}</p>`;
  const overrideByYear = new Map(overrides.map(item => [item.year, item]));
  const input = (row, field, value, percent = false) => {
    if (row.actual) return escapeHtml(money(value));
    if (!editable) return escapeHtml(value == null ? '—' : percent ? formatPercent(Number(value), {maximumFractionDigits: 4}) : money(value));
    const hasOverride = overrideByYear.get(row.year)?.[field] != null;
    const shown = percent ? rateInputValue(value) : Number(value || 0).toFixed(2);
    const fieldLabel = `${t(`salary.${fieldKeys[field]}`)}${percent ? ' (%)' : ''}`;
    const label = t('salary.annual_field', {year: row.year, field: fieldLabel});
    const status = hasOverride
      ? `<span class="fv-badge" data-input-status>${escapeHtml(t('salary.override'))}</span>${iconAction('reset', {label: t('actions.reset', {name: label}), attributes: {'data-salary-use-default': '', 'data-year': row.year, 'data-field': field}})}`
      : `<span class="field-note" data-input-status>${escapeHtml(t('salary.calculated_default'))}</span>`;
    return `<span class="salary-input-cell"><input aria-label="${escapeHtml(label)}" class="fv-input salary-year-input${hasOverride ? ' manual-override' : ''}" data-year="${row.year}" data-field="${field}" data-original="${escapeHtml(shown)}" data-has-override="${hasOverride}" type="number" step="${percent ? '0.0001' : '0.01'}" value="${escapeHtml(shown)}"><span class="salary-input-status">${status}</span></span>`;
  };
  const detail = (label, value) => `<div class="salary-detail-field"><dt>${escapeHtml(label)}</dt><dd>${value}</dd></div>`;
  const record = row => {
    const key = `${row.actual ? 'actual' : 'projection'}-${row.year}`;
    const open = expandedRows.has(key);
    const id = `salary-details-${key}`;
    const name = t('salary.year_details', {year: row.year});
    const values = [
      detail(t('salary.age'), escapeHtml(row.age ?? '—')),
      detail(`${t('salary.raise')} (%)`, row.actual ? '—' : input(row, 'raise_rate', row.raise_rate, true)),
      detail(t('salary.annual_salary'), input(row, 'salary', row.annual_salary_rate)),
      detail(t('salary.other_income'), input(row, 'other_income', row.other_income)),
      detail(t('salary.gross'), money(row.gross_income)),
      detail(t('salary.rrsp_cash'), input(row, 'rrsp_contribution', row.rrsp_contribution)),
      detail(t('salary.rrsp_deduction'), input(row, 'rrsp_deduction', row.rrsp_deduction)),
      ...[['financial.cpp_qpp', 'cpp_qpp'], ['financial.ei', 'ei'], ['financial.qpip', 'qpip'], ['salary.federal_tax', 'federal_tax'], ['salary.quebec_tax', 'quebec_tax'], ['salary.net_after_tax', 'net_income_after_tax']].map(([label, field]) => detail(t(label), money(row[field]))),
      ...(household ? [detail(t('salary.expenses'), row.planned_expenses == null ? '—' : money(row.planned_expenses)), detail(t('salary.surplus_deficit'), row.surplus_deficit == null ? '—' : money(row.surplus_deficit))] : []),
      detail(t('salary.rule_source'), row.actual ? escapeHtml(incomeSourceLabel(row.source) || t('salary.recorded')) : `${escapeHtml(row.rule_year)}${row.rules_held_constant ? ` ${escapeHtml(t('salary.held'))}` : ''}`),
    ].join('');
    return `<tr class="salary-summary-row${row.actual ? ' historical-row' : ''}"><th scope="row"><span class="salary-summary-year">${escapeHtml(row.year)}${row.actual ? ` ${escapeHtml(t('salary.actual'))}` : ''}</span></th>
      <td class="salary-summary-gross">${money(row.gross_income)}</td><td class="salary-disposable"><strong>${money(row.disposable_income)}</strong></td>
      ${household ? `<td class="salary-summary-extra">${row.planned_expenses == null ? '—' : money(row.planned_expenses)}</td><td class="salary-summary-extra">${row.surplus_deficit == null ? '—' : money(row.surplus_deficit)}</td>` : ''}
      <td>${iconAction(open ? 'collapse' : 'expand', {label: t(open ? 'actions.collapse' : 'actions.expand', {name}), attributes: {'data-year-details': key, 'data-detail-name': name, 'aria-expanded': String(open), 'aria-controls': id}})}</td></tr>
      <tr id="${escapeHtml(id)}" class="salary-detail-row"${open ? '' : ' hidden'}><td data-summary-span="${household ? 6 : 4}" colspan="${household ? 6 : 4}"><section aria-labelledby="${escapeHtml(id)}-heading"><h3 id="${escapeHtml(id)}-heading">${escapeHtml(name)}</h3><dl class="salary-details-grid">${values}</dl>${editable && !row.actual ? `<div class="salary-year-editor" data-year-editor="${escapeHtml(row.year)}"><p class="fv-help">${escapeHtml(t('salary.year_save_scope'))}</p><div class="salary-year-actions"><button type="button" class="fv-button" data-year-cancel="${escapeHtml(row.year)}" disabled>${escapeHtml(t('salary.cancel'))}</button><button type="button" class="fv-button fv-button--primary" data-year-save="${escapeHtml(row.year)}" disabled>${escapeHtml(t('salary.save'))}</button></div><p data-year-message="${escapeHtml(row.year)}" class="fv-feedback" role="status" tabindex="-1" hidden></p></div>` : ''}</section></td></tr>`;
  };
  const section = (label, entries, className) => entries.length ? `<tbody class="${className}"><tr class="salary-section-row"><th data-summary-span="${household ? 6 : 4}" colspan="${household ? 6 : 4}">${escapeHtml(label)}</th></tr>${entries.map(record).join('')}</tbody>` : '';
  return `<div class="table-wrap fv-table-scroll" tabindex="0" role="region" aria-label="${escapeHtml(t('salary.results'))}" aria-describedby="salary-scroll-hint"><table class="salary-projection-table fv-table${household ? ' salary-household-table' : ''}"><caption>${escapeHtml(t('salary.results'))}</caption><thead><tr>
    <th class="salary-year-heading">${t('salary.year')}</th><th class="salary-summary-gross">${t('salary.gross')}</th><th class="salary-disposable">${t('salary.disposable')}</th>${household ? `<th class="salary-summary-extra">${t('salary.expenses')}</th><th class="salary-summary-extra">${t('salary.surplus_deficit')}</th>` : ''}<th class="salary-detail-heading">${t('salary.details')}</th></tr></thead>
    ${section(t('salary.historical'), rows.filter(row => row.actual), 'salary-history-body')}${section(t('salary.projected'), rows.filter(row => !row.actual), 'salary-projection-body')}</table></div>`;
}
