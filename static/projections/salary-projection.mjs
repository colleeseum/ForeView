// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {escapeHtml} from '../shared/html.mjs';
import {t, locale} from '../shared/i18n.mjs';
import {formatMoneyDollars, formatPercent} from '../shared/locale-format.mjs';
import {formSignature} from '../shared/form-state.mjs';
import {incomeSourceLabel} from '../shared/income-source-label.mjs';
import {createDialog} from '../shared/dialog.mjs';

const elements = {
  scenario: document.querySelector('#salary-scenario'),
  startYear: document.querySelector('#salary-start-year'),
  endYear: document.querySelector('#salary-end-year'),
  view: document.querySelector('#salary-view'),
  message: document.querySelector('#salary-message'),
  tabs: document.querySelector('#salary-tabs'),
  setup: document.querySelector('#salary-setup'),
  expenseSetup: document.querySelector('#salary-expense-setup'),
  sourceNote: document.querySelector('#salary-source-note'),
  currentRate: document.querySelector('#salary-current-rate'),
  currentYear: document.querySelector('#salary-current-year'),
  currentProvince: document.querySelector('#salary-current-province'),
  currentPayroll: document.querySelector('#salary-current-payroll'),
  currentRrspContribution: document.querySelector('#salary-current-rrsp-contribution'),
  currentRrspDeduction: document.querySelector('#salary-current-rrsp-deduction'),
  currentOtherIncome: document.querySelector('#salary-current-other-income'),
  form: document.querySelector('#salary-settings-form'),
  expenseForm: document.querySelector('#salary-expense-form'),
  expenseSave: document.querySelector('#salary-expense-save'),
  expenseStatus: document.querySelector('#salary-expense-status'),
  save: document.querySelector('#salary-save'),
  saveAs: document.querySelector('#salary-save-as'),
  discard: document.querySelector('#salary-discard'),
  changeStatus: document.querySelector('#salary-change-status'),
  saveAsBackdrop: document.querySelector('#salary-save-as-backdrop'),
  saveAsClose: document.querySelector('#salary-save-as-close'),
  saveAsForm: document.querySelector('#salary-save-as-form'),
  saveAsMessage: document.querySelector('#salary-save-as-message'),
  table: document.querySelector('#salary-table'),
};

let model = null;
let selectedKey = null;
let savedFormSignature = '';
let savedExpenseSignature = '';
const pendingAnnualChanges = new Map();
const pendingAnnualResets = new Set();
let busy = false;
let readScenario = null;
let readGeneration = 0;
const root = document.querySelector('.fv-salary') || document.body;
const cloneDialog = elements.saveAsBackdrop ? createDialog(elements.saveAsBackdrop, {fallbackFocus: elements.saveAs}) : null;
elements.saveAsBackdrop?.addEventListener('close', () => {if (!elements.saveAsBackdrop.open) elements.saveAsBackdrop.hidden = true;});
elements.saveAsBackdrop?.addEventListener('cancel', event => {if (busy) event.preventDefault();});
root.querySelectorAll('button').forEach(node => node.classList.add('fv-button'));
root.querySelectorAll('input, select').forEach(node => node.classList.add('fv-input'));
for (const button of [elements.save, elements.expenseSave, elements.saveAsForm?.querySelector('[type="submit"]')]) button?.classList.add('fv-button--primary');

function lock(value) {
  busy = value;
  root.setAttribute('aria-busy', String(value));
  root.querySelectorAll('input, select, button').forEach(node => {node.disabled = value;});
  if (!value) updateSaveState();
}

export function money(value) {
  return formatMoneyDollars(value ?? 0);
}

export function projectionTable(rows, {editable = false, overrides = [], household = false} = {}) {
  if (!rows.length) return `<p class="empty-panel">${t('salary.no_projection')}</p>`;
  const overrideByYear = new Map(overrides.map((item) => [item.year, item]));
  const input = (row, field, value, suffix = '') => {
    if (!editable) return escapeHtml(value == null ? '—' : suffix ? formatPercent(Number(value), {maximumFractionDigits: 3}) : money(value));
    const override = overrideByYear.get(row.year)?.[field];
    const hasOverride = override != null;
    const shown = field === 'raise_rate'
      ? (Number(value || 0) * 100).toFixed(3).replace(/0+$/, '').replace(/\.$/, '')
      : Number(value || 0).toFixed(2);
    const reset = hasOverride
      ? `<span class="fv-badge">${escapeHtml(t('salary.override'))}</span><button class="salary-use-default fv-button" data-year="${row.year}" data-field="${field}" type="button" title="${t('salary.reset')}" aria-label="${escapeHtml(t('salary.annual_field', {year: row.year, field: t('salary.reset')}))}">×</button>`
      : '';
    return `<span class="salary-input-cell"><input aria-label="${escapeHtml(t('salary.annual_field', {year: row.year, field: t(`salary.${field === 'salary' ? 'annual_salary' : field === 'raise_rate' ? 'raise' : field === 'rrsp_contribution' ? 'rrsp_cash' : field === 'rrsp_deduction' ? 'rrsp_deduction' : 'other_income'}`)}))}" class="fv-input salary-year-input${hasOverride ? ' manual-override' : ''}" data-year="${row.year}" data-field="${field}" data-original="${escapeHtml(shown)}" data-has-override="${hasOverride}" type="number" step="0.01" value="${escapeHtml(shown)}">${reset}</span>${suffix}`;
  };
  const rowMarkup = (row) => `<tr class="${row.actual ? 'historical-row' : ''}">
    <th scope="row">${escapeHtml(String(row.year))}${row.actual ? ` ${t('salary.actual')}` : ''}</th>
    <td>${row.age ?? '—'}</td>
    <td>${row.actual ? '—' : input(row, 'raise_rate', row.raise_rate, '%')}</td>
    <td>${row.actual ? money(row.annual_salary_rate) : input(row, 'salary', row.annual_salary_rate)}</td>
    <td>${row.actual ? money(row.other_income) : input(row, 'other_income', row.other_income)}</td>
    <td>${money(row.gross_income)}</td>
    <td>${row.actual ? money(row.rrsp_contribution) : input(row, 'rrsp_contribution', row.rrsp_contribution)}</td>
    <td>${row.actual ? money(row.rrsp_deduction) : input(row, 'rrsp_deduction', row.rrsp_deduction)}</td>
    <td>${money(row.cpp_qpp)}</td><td>${money(row.ei)}</td><td>${money(row.qpip)}</td>
    <td>${money(row.federal_tax)}</td><td>${money(row.quebec_tax)}</td>
    <td>${money(row.net_income_after_tax)}</td><td><strong>${money(row.disposable_income)}</strong></td>
    ${household ? `<td>${row.planned_expenses == null ? '—' : money(row.planned_expenses)}</td><td><strong>${row.surplus_deficit == null ? '—' : money(row.surplus_deficit)}</strong></td>` : ''}
    <td>${row.actual ? escapeHtml(incomeSourceLabel(row.source) || t('salary.recorded')) : `${row.rule_year}${row.rules_held_constant ? ` ${t('salary.held')}` : ''}`}</td>
  </tr>`;
  const actualRows = rows.filter((row) => row.actual);
  const projectedRows = rows.filter((row) => !row.actual);
  const section = (label, sectionRows, className) => sectionRows.length
    ? `<tbody class="${className}"><tr class="salary-section-row"><th colspan="${household ? 18 : 16}">${label}</th></tr>${sectionRows.map(rowMarkup).join('')}</tbody>`
    : '';
  return `<div class="table-wrap fv-table-scroll" tabindex="0" role="region" aria-label="${escapeHtml(t('salary.results'))}" aria-describedby="salary-scroll-hint"><table class="salary-projection-table fv-table"><caption>${escapeHtml(t('salary.results'))}</caption><thead><tr>
    <th>${t('salary.year')}</th><th>${t('salary.age')}</th><th>${t('salary.raise')}</th><th>${t('salary.annual_salary')}</th>
    <th>${t('salary.other_income')}</th><th>${t('salary.gross')}</th>
    <th>${t('salary.rrsp_cash')}</th><th>${t('salary.rrsp_deduction')}</th><th>${t('financial.cpp_qpp')}</th>
    <th>${t('financial.ei')}</th><th>${t('financial.qpip')}</th><th>${t('salary.federal_tax')}</th><th>${t('salary.quebec_tax')}</th><th>${t('salary.net_after_tax')}</th>
    <th>${t('salary.disposable')}</th>${household ? `<th>${t('salary.expenses')}</th><th>${t('salary.surplus_deficit')}</th>` : ''}<th>${t('salary.rule_source')}</th></tr></thead>
    ${section(t('salary.historical'), actualRows, 'salary-history-body')}
    ${section(t('salary.projected'), projectedRows, 'salary-projection-body')}
  </table></div>`;
}

export function householdRows(rows) {
  return rows.map((row) => ({...row, age: null, rule_year: '—', rules_held_constant: false}));
}

function showMessage(value, error = false, language = locale) {
  elements.message.textContent = value;
  elements.message.classList.toggle('error', error);
  elements.message.lang = language;
  elements.message.setAttribute('role', error ? 'alert' : 'status');
}

function showError(error) {
  showMessage(error.message, true, error.language || 'en-CA');
}

function selectedPerson() {
  return model?.people.find((person) => String(person.id) === selectedKey) || null;
}

function isDirty() {
  return Boolean(selectedPerson()) && (
    formSignature(elements.form) !== savedFormSignature || pendingAnnualChanges.size > 0
  );
}

function expenseDirty() {
  return Boolean(model?.selected_scenario_id && elements.expenseForm)
    && formSignature(elements.expenseForm) !== savedExpenseSignature;
}

function updateSaveState() {
  if (busy) return;
  const assumptionsDirty = Boolean(selectedPerson()) && formSignature(elements.form) !== savedFormSignature;
  const dirty = isDirty() || expenseDirty();
  if (elements.save) elements.save.disabled = !isDirty();
  if (elements.discard) elements.discard.disabled = !dirty;
  if (elements.saveAs) elements.saveAs.disabled = !model?.selected_scenario_id || expenseDirty();
  if (elements.expenseSave) elements.expenseSave.disabled = !expenseDirty();
  if (elements.changeStatus) {
    const changes = [];
    if (assumptionsDirty) {
      changes.push(elements.changeStatus.dataset.assumptionsText || t('salary.projection_assumptions'));
    }
    if (pendingAnnualChanges.size) {
      const template = pendingAnnualChanges.size === 1
        ? elements.changeStatus.dataset.annualChangeText || t('salary.annual_change', {count: '{count}'})
        : elements.changeStatus.dataset.annualChangesText || t('salary.annual_changes', {count: '{count}'});
      changes.push(template.replace('{count}', String(pendingAnnualChanges.size)));
    }
    if (expenseDirty()) {
      changes.push(elements.changeStatus.dataset.spendingText || t('salary.household_spending'));
    }
    const conjunction = ` ${elements.changeStatus.dataset.andText || t('salary.and')} `;
    const changeSummary = changes.length > 1
      ? `${changes.slice(0, -1).join(', ')}${conjunction}${changes.at(-1)}`
      : changes[0] || '';
    const notSaved = elements.changeStatus.dataset.notSavedText || t('salary.not_saved', {changes: '{changes}'});
    elements.changeStatus.textContent = dirty
      ? notSaved.replace('{changes}', changeSummary)
      : elements.changeStatus.dataset.savedText || t('salary.changes_saved');
  }
  for (const control of [elements.scenario, elements.startYear, elements.endYear, elements.view]) {
    if (control) control.disabled = dirty;
  }
  elements.tabs?.querySelectorAll('button').forEach((button) => { button.disabled = dirty; });
  elements.form?.querySelectorAll('input').forEach(node => {node.disabled = expenseDirty() || !selectedPerson();});
  elements.table?.querySelectorAll('input, button').forEach(node => {node.disabled = expenseDirty();});
  elements.expenseForm?.querySelectorAll('input').forEach(node => {node.disabled = isDirty();});
}

function renderControls() {
  elements.scenario.innerHTML = model.scenarios.map((item) => `<option value="${item.id}"${item.id === model.selected_scenario_id ? ' selected' : ''}>${escapeHtml(item.name)}</option>`).join('');
  elements.startYear.value = model.start_year;
  elements.endYear.value = model.end_year;
  elements.tabs.innerHTML = [...model.people.map((person) => ({key: String(person.id), label: person.name})), {key: 'household', label: t('salary.household')}]
    .map((item) => `<button class="view-tab fv-button${item.key === selectedKey ? ' active' : ''}" aria-pressed="${item.key === selectedKey}" data-person-key="${item.key}" type="button">${escapeHtml(item.label)}</button>`).join('');
}

function fillForm(person) {
  elements.setup.hidden = !person || !model.selected_scenario_id;
  if (!person || !model.selected_scenario_id) return;
  const settings = person.settings || {};
  const values = {
    default_raise: settings.default_raise == null ? '0' : Number(settings.default_raise) * 100,
    retirement_date: settings.retirement_date || '',
  };
  Object.entries(values).forEach(([name, value]) => { elements.form.elements[name].value = value; });
  savedFormSignature = formSignature(elements.form);
  const anchor = person.salary_anchor;
  if (elements.currentRate) elements.currentRate.textContent = anchor ? money(anchor.annual_salary_rate) : '—';
  if (elements.currentYear) elements.currentYear.textContent = anchor ? String(anchor.year) : '—';
  if (elements.currentProvince) elements.currentProvince.textContent = anchor?.province_of_employment || '—';
  if (elements.currentPayroll) elements.currentPayroll.textContent = anchor?.payroll_plan || '—';
  if (elements.currentRrspContribution) elements.currentRrspContribution.textContent = anchor ? money(anchor.rrsp_contribution) : '—';
  if (elements.currentRrspDeduction) elements.currentRrspDeduction.textContent = anchor ? money(anchor.rrsp_deduction) : '—';
  if (elements.currentOtherIncome) elements.currentOtherIncome.textContent = anchor ? money(anchor.other_income) : '—';
  if (elements.sourceNote) {
    elements.sourceNote.innerHTML = person.salary_anchor
      ? `<span>${escapeHtml(t('salary.source_note', {year: person.salary_anchor.year, amount: money(person.salary_anchor.annual_salary_rate)}))}</span> <a href="/income">${escapeHtml(t('salary.view_income'))}</a>.`
      : `<span>${escapeHtml(t('salary.no_source'))}</span> <a href="/income">${escapeHtml(t('salary.go_to_income'))}</a>.`;
  }
}

function fillExpenseForm() {
  if (!elements.expenseSetup || !elements.expenseForm) return;
  const plan = model?.expense_plan;
  elements.expenseSetup.hidden = !model?.selected_scenario_id;
  if (!model?.selected_scenario_id) return;
  const values = {
    start_year: plan?.start_year ?? model.start_year,
    required_annual_amount: plan?.required_annual_amount ?? '0.00',
    required_annual_growth: plan?.required_annual_growth == null ? '0' : Number(plan.required_annual_growth) * 100,
    discretionary_annual_amount: plan?.discretionary_annual_amount ?? '0.00',
    discretionary_annual_growth: plan?.discretionary_annual_growth == null ? '0' : Number(plan.discretionary_annual_growth) * 100,
  };
  Object.entries(values).forEach(([name, value]) => { elements.expenseForm.elements[name].value = value; });
  savedExpenseSignature = formSignature(elements.expenseForm);
  if (elements.expenseStatus) elements.expenseStatus.textContent = plan ? t('salary.saved') : t('salary.no_spending');
}

function render() {
  pendingAnnualChanges.clear();
  pendingAnnualResets.clear();
  if (!model.scenarios.length) {
    elements.tabs.innerHTML = '';
    elements.setup.hidden = true;
    if (elements.expenseSetup) elements.expenseSetup.hidden = true;
    elements.scenario.replaceChildren();
    elements.table.innerHTML = `<p class="empty-panel"><span>${escapeHtml(t('salary.no_scenario'))}</span> <a href="/setup">${escapeHtml(t('salary.go_to_setup'))}</a>.</p>`;
    updateSaveState();
    return;
  }
  if (selectedKey !== 'household' && !model.people.some(person => String(person.id) === selectedKey)) selectedKey = null;
  if (!selectedKey) selectedKey = model.people[0] ? String(model.people[0].id) : 'household';
  renderControls();
  const person = selectedPerson();
  fillForm(person);
  fillExpenseForm();
  if (person) {
    if (person.error) showMessage(person.error, true, person.error_language || 'en-CA'); else showMessage('');
    elements.table.innerHTML = projectionTable([...person.actuals, ...person.projection], {editable: true, overrides: person.overrides});
  } else {
    showMessage(t('salary.household_note'));
    elements.table.innerHTML = projectionTable(householdRows(model.household), {household: true});
  }
  elements.table.querySelectorAll('thead th').forEach(node => {node.scope = 'col';});
  updateSaveState();
}

async function api(url, options) {
  const response = await fetch(url, {headers: {'Content-Type': 'application/json'}, ...options});
  let result;
  try {result = await response.json();}
  catch {
    const error = new Error(t('salary.request_failed'));
    error.language = locale;
    throw error;
  }
  if (!response.ok) {
    const error = new Error(result?.error || t('salary.request_failed'));
    error.language = result?.error ? (result.error_language || 'en-CA') : locale;
    throw error;
  }
  return result;
}

export async function loadProjection(scenarioId = elements.scenario.value) {
  const generation = ++readGeneration;
  readScenario = scenarioId;
  const query = new URLSearchParams();
  if (scenarioId) query.set('scenario_id', scenarioId);
  if (elements.startYear.value) query.set('start_year', elements.startYear.value);
  if (elements.endYear.value) query.set('end_year', elements.endYear.value);
  const result = await api(`/api/salary-projection?${query}`);
  if (generation !== readGeneration) return model;
  model = result;
  render();
  return model;
}

async function readProjection(scenarioId = readScenario ?? elements.scenario.value, savedMessage = '') {
  lock(true);
  try {
    await loadProjection(scenarioId);
    if (savedMessage) {
      showMessage(savedMessage);
      const person = selectedPerson();
      if (person?.error) {
        const warning = document.createElement('span');
        warning.lang = person.error_language || 'en-CA';
        warning.textContent = person.error;
        elements.message.append(' ', warning);
        elements.message.setAttribute('role', 'alert');
      }
    }
  } catch (error) {
    model = null;
    elements.setup.hidden = true;
    if (elements.expenseSetup) elements.expenseSetup.hidden = true;
    elements.tabs.replaceChildren();
    elements.table.replaceChildren();
    showMessage(savedMessage ? `${savedMessage} ${t('salary.refresh_failed')}` : error.message, true, savedMessage ? locale : error.language || 'en-CA');
    const retry = document.createElement('button');
    retry.type = 'button';
    retry.className = 'fv-button';
    retry.textContent = t('salary.retry');
    retry.addEventListener('click', () => {if (!busy) readProjection(scenarioId, savedMessage);});
    elements.message.append(' ', retry);
  } finally {lock(false);}
}

elements.tabs?.addEventListener('click', (event) => {
  const tab = event.target.closest('[data-person-key]');
  if (!tab || busy || isDirty() || expenseDirty()) return;
  selectedKey = tab.dataset.personKey;
  render();
});

elements.view?.addEventListener('click', () => {if (!busy && !isDirty() && !expenseDirty()) readProjection(elements.scenario.value);});
elements.scenario?.addEventListener('change', () => {if (!busy && !isDirty() && !expenseDirty()) readProjection(elements.scenario.value);});
elements.form?.addEventListener('input', updateSaveState);
elements.form?.addEventListener('change', updateSaveState);
elements.expenseForm?.addEventListener('input', updateSaveState);
elements.expenseForm?.addEventListener('change', updateSaveState);

function annualOverridePayload(person) {
  const byYear = new Map();
  for (const change of pendingAnnualChanges.values()) {
    const existing = person.overrides.find((item) => item.year === change.year) || {year: change.year};
    const payload = byYear.get(change.year) || {
      year: change.year, salary: existing.salary, raise_rate: existing.raise_rate,
      rrsp_contribution: existing.rrsp_contribution, rrsp_deduction: existing.rrsp_deduction,
      other_income: existing.other_income,
    };
    payload[change.field] = pendingAnnualResets.has(`${change.year}:${change.field}`)
      ? null
      : change.field === 'raise_rate' ? Number(change.value) / 100 : change.value;
    byYear.set(change.year, payload);
  }
  return [...byYear.values()];
}

function draftPayload(person) {
  const values = Object.fromEntries(new FormData(elements.form));
  return {
    person_id: person.id,
    settings: {
      default_raise: Number(values.default_raise || 0) / 100,
      retirement_date: values.retirement_date,
    },
    overrides: annualOverridePayload(person),
  };
}

async function saveCurrentScenario() {
  const person = selectedPerson();
  if (!person || busy || expenseDirty() || !isDirty() || !elements.form.reportValidity()) return;
  const payload = draftPayload(person);
  const scenarioId = model.selected_scenario_id;
  lock(true);
  try {
    await api(`/api/salary-projection/scenarios/${scenarioId}/people/${person.id}/draft`, {
      method: 'PUT', body: JSON.stringify(payload),
    });
  } catch (error) {lock(false); showError(error); return;}
  await readProjection(scenarioId, t('salary.scenario_saved'));
}

elements.form?.addEventListener('submit', (event) => {
  event.preventDefault();
  if (isDirty()) saveCurrentScenario();
});
elements.save?.addEventListener('click', saveCurrentScenario);

async function saveExpenses(event) {
  event?.preventDefault();
  if (busy || isDirty() || !model?.selected_scenario_id || !elements.expenseForm.reportValidity()) return;
  const scenarioId = model.selected_scenario_id;
  const values = Object.fromEntries(new FormData(elements.expenseForm));
  lock(true);
  try {
    await api(`/api/salary-projection/scenarios/${scenarioId}/expenses`, {
      method: 'PUT', body: JSON.stringify({
        start_year: Number(values.start_year),
        required_annual_amount: values.required_annual_amount,
        required_annual_growth: Number(values.required_annual_growth || 0) / 100,
        discretionary_annual_amount: values.discretionary_annual_amount,
        discretionary_annual_growth: Number(values.discretionary_annual_growth || 0) / 100,
      }),
    });
  } catch (error) {lock(false); showError(error); return;}
  await readProjection(scenarioId, t('salary.spending_saved'));
}

elements.expenseForm?.addEventListener('submit', saveExpenses);

elements.table?.addEventListener('input', (event) => {
  const input = event.target.closest('.salary-year-input');
  const person = selectedPerson();
  if (!input || !person || busy || expenseDirty()) return;
  const key = `${input.dataset.year}:${input.dataset.field}`;
  const hasOverride = input.dataset.hasOverride === 'true';
  const unchanged = (!hasOverride && input.value === '')
    || (input.value !== '' && Number(input.value) === Number(input.dataset.original));
  if (unchanged) {
    pendingAnnualChanges.delete(key);
    pendingAnnualResets.delete(key);
    input.classList.remove('pending-change');
    input.classList.remove('pending-reset');
  } else {
    pendingAnnualChanges.set(key, {
      year: Number(input.dataset.year), field: input.dataset.field, value: input.value,
    });
    pendingAnnualResets.delete(key);
    input.classList.remove('pending-reset');
    input.classList.add('pending-change');
  }
  updateSaveState();
});

elements.table?.addEventListener('click', (event) => {
  const reset = event.target.closest('.salary-use-default');
  if (!reset || busy || expenseDirty()) return;
  const input = elements.table.querySelector(
    `.salary-year-input[data-year="${reset.dataset.year}"][data-field="${reset.dataset.field}"]`,
  );
  if (!input) return;
  const key = `${reset.dataset.year}:${reset.dataset.field}`;
  pendingAnnualResets.add(key);
  pendingAnnualChanges.set(key, {
    year: Number(reset.dataset.year), field: reset.dataset.field, value: input.value,
  });
  input.classList.remove('manual-override');
  input.classList.remove('pending-change');
  input.classList.add('pending-reset');
  updateSaveState();
});

elements.discard?.addEventListener('click', () => {if (!busy && model) render();});

function openSaveAs() {
  if (!elements.saveAsBackdrop || !elements.saveAsForm || !model?.selected_scenario_id || busy || expenseDirty()) return;
  const current = model.scenarios.find((item) => item.id === model.selected_scenario_id);
  elements.saveAsForm.elements.name.value = t('salary.scenario_copy', {name: current?.name || t('salary.scenario')});
  if (elements.saveAsMessage) {
    elements.saveAsMessage.textContent = '';
    elements.saveAsMessage.lang = locale;
  }
  elements.saveAsBackdrop.hidden = false;
  cloneDialog.open();
  elements.saveAsForm.elements.name.focus();
  elements.saveAsForm.elements.name.select();
}

elements.saveAs?.addEventListener('click', openSaveAs);
elements.saveAsClose?.addEventListener('click', () => {if (!busy) cloneDialog.close();});
elements.saveAsBackdrop?.addEventListener('click', event => {if (busy && event.target.closest('[data-dialog-close]')) event.stopImmediatePropagation();}, true);
elements.saveAsForm?.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (busy || !model?.selected_scenario_id || expenseDirty() || !elements.saveAsForm.reportValidity()) return;
  const person = selectedPerson();
  const payload = person && isDirty() ? draftPayload(person) : {overrides: []};
  payload.name = elements.saveAsForm.elements.name.value;
  const scenarioId = model.selected_scenario_id;
  lock(true);
  let result;
  try {
    result = await api(`/api/salary-projection/scenarios/${scenarioId}/clone`, {
      method: 'POST', body: JSON.stringify(payload),
    });
  } catch (error) {
    lock(false);
    if (elements.saveAsMessage) {
      elements.saveAsMessage.textContent = error.message;
      elements.saveAsMessage.lang = error.language || 'en-CA';
      elements.saveAsMessage.setAttribute('role', 'alert');
    }
    return;
  }
  cloneDialog.close();
  await readProjection(result.id, t('salary.scenario_created', {name: result.name}));
  elements.saveAs?.focus();
});

if (elements.table) readProjection(elements.scenario.value);
