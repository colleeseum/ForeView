// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {escapeHtml} from '../shared/html.mjs';
import {t, locale} from '../shared/i18n.mjs';
import {formatMoneyDollars} from '../shared/locale-format.mjs';
import {formSignature} from '../shared/form-state.mjs';
import {initializeIconActions} from '../shared/icon-actions.mjs';
import {projectionTable, rateInputValue} from './projection-table.mjs';
export {projectionTable};
import {createDialog} from '../shared/dialog.mjs';

initializeIconActions();

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
const expandedYearDetails = new Map();
const detailContext = () => `${model?.selected_scenario_id}:${selectedKey}`;
let busy = false;
let readScenario = null;
let readGeneration = 0;
let annualReadRecovery = null;
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
  if (annualReadRecovery) {
    root.querySelectorAll('input, select, button:not(.full-help-button)').forEach(node => {node.disabled = true;});
    root.querySelectorAll('[data-annual-read-retry]').forEach(node => {node.disabled = false;});
    return;
  }
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
  elements.table?.querySelectorAll('input, button:not([data-year-details])').forEach(node => {node.disabled = expenseDirty();});
  elements.expenseForm?.querySelectorAll('input').forEach(node => {node.disabled = isDirty();});
  elements.table?.querySelectorAll('[data-year-save], [data-year-cancel]').forEach(button => {
    const year = Number(button.dataset.yearSave || button.dataset.yearCancel);
    button.disabled = expenseDirty() || !selectedPerson() || !hasYearChanges(year);
  });
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
    default_raise: rateInputValue(settings.default_raise),
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
    required_annual_growth: rateInputValue(plan?.required_annual_growth),
    discretionary_annual_amount: plan?.discretionary_annual_amount ?? '0.00',
    discretionary_annual_growth: rateInputValue(plan?.discretionary_annual_growth),
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
    elements.table.innerHTML = projectionTable([...person.actuals, ...person.projection], {editable: true, overrides: person.overrides, expandedRows: expandedYearDetails.get(detailContext())});
  } else {
    showMessage(t('salary.household_note'));
    elements.table.innerHTML = projectionTable(householdRows(model.household), {household: true, expandedRows: expandedYearDetails.get(detailContext())});
  }
  // Preserve the existing reset selector on controls inserted by each refresh.
  elements.table.querySelectorAll('[data-salary-use-default]').forEach(node => node.classList.add('salary-use-default'));
  resizeSummaryColumns();
  elements.table.querySelectorAll('thead th').forEach(node => {node.scope = 'col';});
  updateSaveState();
}

// Keep spanning detail/section rows aligned when secondary summary columns hide.
function resizeSummaryColumns() {
  const compact = window.matchMedia?.('(max-width: 40rem)').matches ?? false;
  elements.table?.querySelectorAll('[data-summary-span]').forEach(cell => {
    cell.colSpan = compact ? 3 : Number(cell.dataset.summarySpan);
  });
}
window.addEventListener('resize', resizeSummaryColumns);

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

async function readProjection(scenarioId = readScenario ?? elements.scenario.value, savedMessage = '', annualContext = null) {
  let refreshed = false;
  lock(true);
  try {
    await loadProjection(scenarioId);
    annualContext?.restore();
    refreshed = true;
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
    if (annualContext) retry.dataset.annualReadRetry = '';
    retry.addEventListener('click', () => {if (!busy) readProjection(scenarioId, savedMessage, annualContext);});
    elements.message.append(' ', retry);
    if (annualContext) {
      const local = document.createElement('div');
      local.className = 'fv-feedback fv-feedback--error';
      local.setAttribute('role', 'alert');
      local.textContent = `${savedMessage} ${t('salary.refresh_failed')}`;
      const localRetry = retry.cloneNode(true);
      localRetry.addEventListener('click', () => {if (!busy) readProjection(scenarioId, savedMessage, annualContext);});
      local.append(' ', localRetry);
      elements.table.append(local);
      elements.message.setAttribute('role', 'status');
    }
  } finally {
    lock(false);
    if (annualContext) {
      const region = elements.table.querySelector('.fv-table-scroll');
      if (region) {region.scrollTop = annualContext.tableTop; region.scrollLeft = annualContext.tableLeft;}
      if (window.scrollY !== annualContext.top || window.scrollX !== annualContext.left) window.scrollTo(annualContext.left, annualContext.top);
      let focus = refreshed ? elements.table.querySelector(`[data-year-message="${annualContext.year}"]`) : elements.table.querySelector('[data-annual-read-retry]');
      if (refreshed && !focus) {
        focus = document.createElement('p');
        focus.className = 'fv-feedback';
        focus.tabIndex = -1;
        focus.setAttribute('role', 'status');
        focus.textContent = savedMessage;
        elements.table.prepend(focus);
      }
      focus?.focus({preventScroll: true});
    }
  }
}

elements.tabs?.addEventListener('click', (event) => {
  const tab = event.target.closest('[data-person-key]');
  if (!tab || busy || annualReadRecovery || isDirty() || expenseDirty()) return;
  selectedKey = tab.dataset.personKey;
  render();
});

elements.view?.addEventListener('click', () => {if (!busy && !annualReadRecovery && !isDirty() && !expenseDirty()) readProjection(elements.scenario.value);});
elements.scenario?.addEventListener('change', () => {if (!busy && !annualReadRecovery && !isDirty() && !expenseDirty()) readProjection(elements.scenario.value);});
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

function hasYearChanges(year) {
  return [...pendingAnnualChanges.values()].some(change => change.year === year);
}

function yearMessage(year, message, error = false, language = locale) {
  const target = elements.table.querySelector(`[data-year-message="${year}"]`);
  if (!target) return;
  target.textContent = message;
  target.lang = language;
  target.hidden = !message;
  target.setAttribute('role', error ? 'alert' : 'status');
  target.classList.toggle('error', error);
}

function annualInputStatus(input) {
  const label = input.closest('.salary-input-cell')?.querySelector('[data-input-status]');
  if (!label) return;
  const key = input.classList.contains('pending-reset') ? 'reset_pending'
    : input.classList.contains('pending-change') ? 'unsaved_value'
      : input.dataset.hasOverride === 'true' ? 'override' : 'calculated_default';
  label.textContent = t(`salary.${key}`);
}

function cancelYear(year) {
  if (busy || annualReadRecovery || expenseDirty() || !hasYearChanges(year)) return;
  elements.table.querySelectorAll(`.salary-year-input[data-year="${year}"]`).forEach(input => {
    input.value = input.dataset.original;
    input.classList.remove('pending-change', 'pending-reset');
    input.classList.toggle('manual-override', input.dataset.hasOverride === 'true');
    annualInputStatus(input);
    const key = `${year}:${input.dataset.field}`;
    pendingAnnualChanges.delete(key);
    pendingAnnualResets.delete(key);
  });
  updateSaveState();
  yearMessage(year, t('salary.year_cancelled', {year}));
  elements.table.querySelector(`[data-year-message="${year}"]`)?.focus({preventScroll: true});
}

async function saveYear(year) {
  const person = selectedPerson();
  if (!person || busy || annualReadRecovery || expenseDirty() || !hasYearChanges(year)) return;
  for (const input of elements.table.querySelectorAll(`.salary-year-input[data-year="${year}"]`)) {
    if (!input.reportValidity()) return;
  }
  const payload = annualOverridePayload(person).find(item => item.year === year);
  const scenarioId = model.selected_scenario_id;
  const settings = formSignature(elements.form) !== savedFormSignature ? Object.fromEntries(new FormData(elements.form)) : null;
  const changes = [...pendingAnnualChanges.values()].filter(change => change.year !== year).map(change => ({...change}));
  const resets = [...pendingAnnualResets].filter(key => !key.startsWith(`${year}:`));
  const region = elements.table.querySelector('.fv-table-scroll');
  const context = {year, top: window.scrollY, left: window.scrollX, tableTop: region?.scrollTop || 0, tableLeft: region?.scrollLeft || 0, restore() {
    if (String(selectedPerson()?.id) !== String(person.id) || String(model.selected_scenario_id) !== String(scenarioId)) throw new Error(t('salary.refresh_failed'));
    if (settings) Object.entries(settings).forEach(([name, value]) => {elements.form.elements[name].value = value;});
    for (const change of changes) {
      const key = `${change.year}:${change.field}`;
      pendingAnnualChanges.set(key, change);
      const input = elements.table.querySelector(`.salary-year-input[data-year="${change.year}"][data-field="${change.field}"]`);
      if (input) {
        input.value = change.value;
        input.classList.add(resets.includes(key) ? 'pending-reset' : 'pending-change');
        if (resets.includes(key)) input.classList.remove('manual-override');
        annualInputStatus(input);
      }
    }
    resets.forEach(key => pendingAnnualResets.add(key));
    annualReadRecovery = null;
    yearMessage(year, t('salary.year_saved', {year}));
  }};
  lock(true);
  yearMessage(year, t('salary.year_saving', {year}));
  try {
    await api(`/api/salary-projection/scenarios/${scenarioId}/people/${person.id}/years/${year}`, {method: 'PUT', body: JSON.stringify(payload)});
  } catch (error) {
    lock(false);
    yearMessage(year, error.message, true, error.language || 'en-CA');
    elements.table.querySelector(`[data-year-message="${year}"]`)?.focus({preventScroll: true});
    return;
  }
  annualReadRecovery = context;
  await readProjection(scenarioId, t('salary.year_saved', {year}), context);
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
  annualInputStatus(input);
  yearMessage(Number(input.dataset.year), hasYearChanges(Number(input.dataset.year)) ? t('salary.year_dirty', {year: input.dataset.year}) : '');
});

elements.table?.addEventListener('click', (event) => {
  const localSave = event.target.closest('[data-year-save]');
  if (localSave) {saveYear(Number(localSave.dataset.yearSave)); return;}
  const localCancel = event.target.closest('[data-year-cancel]');
  if (localCancel) {cancelYear(Number(localCancel.dataset.yearCancel)); return;}
  const disclosure = event.target.closest('[data-year-details]');
  if (disclosure) {
    if (busy) return;
    const row = document.getElementById(disclosure.getAttribute('aria-controls'));
    if (!row) return;
    const open = row.hidden;
    row.hidden = !open;
    const key = disclosure.dataset.yearDetails;
    const expanded = expandedYearDetails.get(detailContext()) || new Set();
    if (open) expanded.add(key); else expanded.delete(key);
    expandedYearDetails.set(detailContext(), expanded);
    disclosure.setAttribute('aria-expanded', String(open));
    disclosure.dataset.iconAction = open ? 'collapse' : 'expand';
    disclosure.setAttribute('aria-label', t(open ? 'actions.collapse' : 'actions.expand', {name: disclosure.dataset.detailName}));
    disclosure.querySelector('.fv-icon').className = `fv-icon fv-icon--${open ? 'collapse' : 'expand'}`;
    return;
  }
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
  annualInputStatus(input);
  updateSaveState();
  yearMessage(Number(reset.dataset.year), t('salary.year_dirty', {year: reset.dataset.year}));
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
