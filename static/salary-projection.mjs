// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {escapeHtml} from './html.mjs';
import {formSignature} from './form-state.mjs';

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

export function money(value) {
  const amount = Number(value || 0);
  return amount.toLocaleString('en-CA', {style: 'currency', currency: 'CAD', maximumFractionDigits: 0});
}

export function projectionTable(rows, {editable = false, overrides = [], household = false} = {}) {
  if (!rows.length) return '<p class="empty-panel">No projection is available.</p>';
  const overrideByYear = new Map(overrides.map((item) => [item.year, item]));
  const input = (row, field, value, suffix = '') => {
    if (!editable) return escapeHtml(value == null ? '—' : suffix ? `${value}${suffix}` : money(value));
    const override = overrideByYear.get(row.year)?.[field];
    const hasOverride = override != null;
    const shown = field === 'raise_rate'
      ? (Number(value || 0) * 100).toFixed(3).replace(/0+$/, '').replace(/\.$/, '')
      : Number(value || 0).toFixed(2);
    const reset = hasOverride
      ? `<button class="salary-use-default" data-year="${row.year}" data-field="${field}" type="button" title="Reset to the calculated default" aria-label="Reset to the calculated default">×</button>`
      : '';
    return `<span class="salary-input-cell"><input class="salary-year-input${hasOverride ? ' manual-override' : ''}" data-year="${row.year}" data-field="${field}" data-original="${escapeHtml(shown)}" data-has-override="${hasOverride}" type="number" step="0.01" value="${escapeHtml(shown)}">${reset}</span>${suffix}`;
  };
  const rowMarkup = (row) => `<tr class="${row.actual ? 'historical-row' : ''}">
    <th>${escapeHtml(String(row.year))}${row.actual ? ' Actual' : ''}</th>
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
    <td>${row.actual ? escapeHtml(row.source || 'Recorded') : `${row.rule_year}${row.rules_held_constant ? ' held' : ''}`}</td>
  </tr>`;
  const actualRows = rows.filter((row) => row.actual);
  const projectedRows = rows.filter((row) => !row.actual);
  const section = (label, sectionRows, className) => sectionRows.length
    ? `<tbody class="${className}"><tr class="salary-section-row"><th colspan="${household ? 18 : 16}">${label}</th></tr>${sectionRows.map(rowMarkup).join('')}</tbody>`
    : '';
  return `<div class="table-wrap"><table class="salary-projection-table"><thead><tr>
    <th>Year</th><th>Age</th><th>Raise</th><th>Annual salary</th>
    <th>Other income</th><th>Gross</th>
    <th>RRSP cash</th><th>RRSP deduction</th><th>CPP/QPP</th>
    <th>EI</th><th>QPIP</th><th>Federal tax</th><th>Quebec tax</th><th>Net after tax</th>
    <th>Disposable</th>${household ? '<th>Expenses</th><th>Surplus / deficit</th>' : ''}<th>Rule/source</th></tr></thead>
    ${section('Historical actuals', actualRows, 'salary-history-body')}
    ${section('Projected values', projectedRows, 'salary-projection-body')}
  </table></div>`;
}

export function householdRows(rows) {
  return rows.map((row) => ({...row, age: null, rule_year: '—', rules_held_constant: false}));
}

function showMessage(value, error = false) {
  elements.message.textContent = value;
  elements.message.classList.toggle('error', error);
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
  const assumptionsDirty = Boolean(selectedPerson()) && formSignature(elements.form) !== savedFormSignature;
  const dirty = isDirty() || expenseDirty();
  if (elements.save) elements.save.disabled = !dirty;
  if (elements.discard) elements.discard.disabled = !dirty;
  if (elements.saveAs) elements.saveAs.disabled = !model?.selected_scenario_id;
  if (elements.expenseSave) elements.expenseSave.disabled = !expenseDirty();
  if (elements.changeStatus) {
    const changes = [];
    if (assumptionsDirty) {
      changes.push(elements.changeStatus.dataset.assumptionsText || 'projection assumptions');
    }
    if (pendingAnnualChanges.size) {
      const template = pendingAnnualChanges.size === 1
        ? elements.changeStatus.dataset.annualChangeText || '{count} annual change'
        : elements.changeStatus.dataset.annualChangesText || '{count} annual changes';
      changes.push(template.replace('{count}', String(pendingAnnualChanges.size)));
    }
    if (expenseDirty()) {
      changes.push(elements.changeStatus.dataset.spendingText || 'household spending');
    }
    const conjunction = ` ${elements.changeStatus.dataset.andText || 'and'} `;
    const changeSummary = changes.length > 1
      ? `${changes.slice(0, -1).join(', ')}${conjunction}${changes.at(-1)}`
      : changes[0] || '';
    const notSaved = elements.changeStatus.dataset.notSavedText || '{changes} not saved.';
    elements.changeStatus.textContent = dirty
      ? notSaved.replace('{changes}', changeSummary)
      : elements.changeStatus.dataset.savedText || 'Changes are saved to the selected scenario. Use Save As to compare alternatives.';
  }
  for (const control of [elements.scenario, elements.startYear, elements.endYear, elements.view]) {
    if (control) control.disabled = dirty;
  }
  elements.tabs?.querySelectorAll('button').forEach((button) => { button.disabled = dirty; });
}

function renderControls() {
  elements.scenario.innerHTML = model.scenarios.map((item) => `<option value="${item.id}"${item.id === model.selected_scenario_id ? ' selected' : ''}>${escapeHtml(item.name)}</option>`).join('');
  elements.startYear.value = model.start_year;
  elements.endYear.value = model.end_year;
  elements.tabs.innerHTML = [...model.people.map((person) => ({key: String(person.id), label: person.name})), {key: 'household', label: 'Household'}]
    .map((item) => `<button class="view-tab${item.key === selectedKey ? ' active' : ''}" role="tab" aria-selected="${item.key === selectedKey}" data-person-key="${item.key}" type="button">${escapeHtml(item.label)}</button>`).join('');
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
      ? `Salary starts from the latest factual Income record: <strong>${escapeHtml(String(person.salary_anchor.year))}</strong>, ${money(person.salary_anchor.annual_salary_rate)} after subtracting the recorded bonus. <a href="/income">View income history</a>.`
      : 'No factual Income record exists. Add one on the <a href="/income">Income</a> screen before projecting employment.';
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
  if (elements.expenseStatus) elements.expenseStatus.textContent = plan ? 'Changes are saved to the selected scenario.' : 'No spending assumptions saved.';
}

function render() {
  pendingAnnualChanges.clear();
  pendingAnnualResets.clear();
  if (!model.scenarios.length) {
    elements.tabs.innerHTML = '';
    elements.setup.hidden = true;
    elements.table.innerHTML = '<p class="empty-panel">Create a scenario in <a href="/setup">Setup</a> before projecting salary.</p>';
    updateSaveState();
    return;
  }
  if (!selectedKey) selectedKey = model.people[0] ? String(model.people[0].id) : 'household';
  renderControls();
  const person = selectedPerson();
  fillForm(person);
  fillExpenseForm();
  if (person) {
    if (person.error) showMessage(person.error, true); else showMessage('');
    elements.table.innerHTML = projectionTable([...person.actuals, ...person.projection], {editable: true, overrides: person.overrides});
  } else {
    showMessage('Household values are the sum of individual projections. Tax remains calculated per person.');
    elements.table.innerHTML = projectionTable(householdRows(model.household), {household: true});
  }
  updateSaveState();
}

async function api(url, options) {
  const response = await fetch(url, {headers: {'Content-Type': 'application/json'}, ...options});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Request failed');
  return result;
}

export async function loadProjection(scenarioId = elements.scenario.value) {
  const query = new URLSearchParams();
  if (scenarioId) query.set('scenario_id', scenarioId);
  if (elements.startYear.value) query.set('start_year', elements.startYear.value);
  if (elements.endYear.value) query.set('end_year', elements.endYear.value);
  model = await api(`/api/salary-projection?${query}`);
  render();
  return model;
}

elements.tabs?.addEventListener('click', (event) => {
  const tab = event.target.closest('[data-person-key]');
  if (!tab) return;
  selectedKey = tab.dataset.personKey;
  render();
});

elements.view?.addEventListener('click', () => loadProjection().catch((error) => showMessage(error.message, true)));
elements.scenario?.addEventListener('change', () => loadProjection().catch((error) => showMessage(error.message, true)));
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
  if (!person) return;
  try {
    await api(`/api/salary-projection/scenarios/${model.selected_scenario_id}/people/${person.id}/draft`, {
      method: 'PUT', body: JSON.stringify(draftPayload(person)),
    });
    await loadProjection();
    showMessage('Scenario saved.');
  } catch (error) { showMessage(error.message, true); }
}

elements.form?.addEventListener('submit', (event) => {
  event.preventDefault();
  if (isDirty()) saveCurrentScenario();
});
elements.save?.addEventListener('click', saveCurrentScenario);

async function saveExpenses(event) {
  event?.preventDefault();
  try {
    const values = Object.fromEntries(new FormData(elements.expenseForm));
    await api(`/api/salary-projection/scenarios/${model.selected_scenario_id}/expenses`, {
      method: 'PUT', body: JSON.stringify({
        start_year: Number(values.start_year),
        required_annual_amount: values.required_annual_amount,
        required_annual_growth: Number(values.required_annual_growth || 0) / 100,
        discretionary_annual_amount: values.discretionary_annual_amount,
        discretionary_annual_growth: Number(values.discretionary_annual_growth || 0) / 100,
      }),
    });
    await loadProjection();
    showMessage('Household spending assumptions saved.');
  } catch (error) { showMessage(error.message, true); }
}

elements.expenseForm?.addEventListener('submit', saveExpenses);

elements.table?.addEventListener('input', (event) => {
  const input = event.target.closest('.salary-year-input');
  const person = selectedPerson();
  if (!input || !person) return;
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
  if (!reset) return;
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

elements.discard?.addEventListener('click', () => render());

function openSaveAs() {
  if (!elements.saveAsBackdrop || !elements.saveAsForm || !model?.selected_scenario_id) return;
  const current = model.scenarios.find((item) => item.id === model.selected_scenario_id);
  elements.saveAsForm.elements.name.value = `${current?.name || 'Scenario'} copy`;
  if (elements.saveAsMessage) elements.saveAsMessage.textContent = '';
  elements.saveAsBackdrop.hidden = false;
  elements.saveAsForm.elements.name.focus();
  elements.saveAsForm.elements.name.select();
}

elements.saveAs?.addEventListener('click', openSaveAs);
elements.saveAsClose?.addEventListener('click', () => { elements.saveAsBackdrop.hidden = true; });
elements.saveAsForm?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const person = selectedPerson();
  const payload = person ? draftPayload(person) : {overrides: []};
  payload.name = elements.saveAsForm.elements.name.value;
  try {
    const result = await api(`/api/salary-projection/scenarios/${model.selected_scenario_id}/clone`, {
      method: 'POST', body: JSON.stringify(payload),
    });
    elements.saveAsBackdrop.hidden = true;
    await loadProjection(result.id);
    showMessage(`Scenario "${result.name}" created.`);
  } catch (error) {
    if (elements.saveAsMessage) elements.saveAsMessage.textContent = error.message;
  }
});

if (elements.table) loadProjection().catch((error) => showMessage(error.message, true));
