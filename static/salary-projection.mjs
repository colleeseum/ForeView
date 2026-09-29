import {escapeHtml} from './html.mjs';

const elements = {
  scenario: document.querySelector('#salary-scenario'),
  startYear: document.querySelector('#salary-start-year'),
  endYear: document.querySelector('#salary-end-year'),
  view: document.querySelector('#salary-view'),
  message: document.querySelector('#salary-message'),
  tabs: document.querySelector('#salary-tabs'),
  setup: document.querySelector('#salary-setup'),
  sourceNote: document.querySelector('#salary-source-note'),
  currentRate: document.querySelector('#salary-current-rate'),
  currentYear: document.querySelector('#salary-current-year'),
  currentProvince: document.querySelector('#salary-current-province'),
  currentPayroll: document.querySelector('#salary-current-payroll'),
  currentRrspContribution: document.querySelector('#salary-current-rrsp-contribution'),
  currentRrspDeduction: document.querySelector('#salary-current-rrsp-deduction'),
  currentOtherIncome: document.querySelector('#salary-current-other-income'),
  form: document.querySelector('#salary-settings-form'),
  table: document.querySelector('#salary-table'),
};

let model = null;
let selectedKey = null;

export function money(value) {
  const amount = Number(value || 0);
  return amount.toLocaleString('en-CA', {style: 'currency', currency: 'CAD', maximumFractionDigits: 0});
}

export function projectionTable(rows, {editable = false, overrides = []} = {}) {
  if (!rows.length) return '<p class="empty-panel">No projection is available.</p>';
  const overrideByYear = new Map(overrides.map((item) => [item.year, item]));
  const input = (row, field, value, suffix = '') => {
    if (!editable) return escapeHtml(value == null ? '—' : suffix ? `${value}${suffix}` : money(value));
    const override = overrideByYear.get(row.year)?.[field];
    const shown = field === 'raise_rate'
      ? (Number(value || 0) * 100).toFixed(3).replace(/0+$/, '').replace(/\.$/, '')
      : Number(value || 0).toFixed(2);
    return `<input class="salary-year-input${override != null ? ' manual-override' : ''}" data-year="${row.year}" data-field="${field}" type="number" step="0.01" value="${escapeHtml(shown)}">${suffix}`;
  };
  const body = rows.map((row) => `<tr class="${row.actual ? 'historical-row' : ''}">
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
    <td>${row.actual ? escapeHtml(row.source || 'Recorded') : `${row.rule_year}${row.rules_held_constant ? ' held' : ''}`}</td>
  </tr>`).join('');
  return `<div class="table-wrap"><table class="salary-projection-table"><thead><tr>
    <th>Year</th><th>Age</th><th>Raise</th><th>Annual salary</th>
    <th>Other income</th><th>Gross</th>
    <th>RRSP cash</th><th>RRSP deduction</th><th>CPP/QPP</th>
    <th>EI</th><th>QPIP</th><th>Federal tax</th><th>Quebec tax</th><th>Net after tax</th>
    <th>Disposable</th><th>Rule/source</th></tr></thead><tbody>${body}</tbody></table></div>`;
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
  const baseline = person.baseline || {};
  const settings = person.settings || {};
  const values = {
    default_raise: settings.default_raise == null ? '0' : Number(settings.default_raise) * 100,
    retirement_date: settings.retirement_date || '',
  };
  Object.entries(values).forEach(([name, value]) => { elements.form.elements[name].value = value; });
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

function render() {
  if (!model.scenarios.length) {
    elements.tabs.innerHTML = '';
    elements.setup.hidden = true;
    elements.table.innerHTML = '<p class="empty-panel">Create a scenario in <a href="/setup">Setup</a> before projecting salary.</p>';
    return;
  }
  if (!selectedKey) selectedKey = model.people[0] ? String(model.people[0].id) : 'household';
  renderControls();
  const person = selectedPerson();
  fillForm(person);
  if (person) {
    if (person.error) showMessage(person.error, true); else showMessage('');
    elements.table.innerHTML = projectionTable([...person.actuals, ...person.projection], {editable: true, overrides: person.overrides});
  } else {
    showMessage('Household values are the sum of individual projections. Tax remains calculated per person.');
    elements.table.innerHTML = projectionTable(householdRows(model.household));
  }
}

async function api(url, options) {
  const response = await fetch(url, {headers: {'Content-Type': 'application/json'}, ...options});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Request failed');
  return result;
}

export async function loadProjection() {
  const query = new URLSearchParams();
  if (elements.scenario.value) query.set('scenario_id', elements.scenario.value);
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

elements.form?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const person = selectedPerson();
  if (!person) return;
  const values = Object.fromEntries(new FormData(elements.form));
  try {
    await api(`/api/salary-projection/scenarios/${model.selected_scenario_id}/people/${person.id}/settings`, {method: 'PUT', body: JSON.stringify({
      default_raise: Number(values.default_raise || 0) / 100, retirement_date: values.retirement_date,
    })});
    showMessage('Projection settings saved.');
    await loadProjection();
  } catch (error) { showMessage(error.message, true); }
});

elements.table?.addEventListener('change', async (event) => {
  const input = event.target.closest('.salary-year-input');
  const person = selectedPerson();
  if (!input || !person) return;
  const year = Number(input.dataset.year);
  const existing = person.overrides.find((item) => item.year === year) || {year};
  const payload = {salary: existing.salary, raise_rate: existing.raise_rate, rrsp_contribution: existing.rrsp_contribution, rrsp_deduction: existing.rrsp_deduction, other_income: existing.other_income};
  payload[input.dataset.field] = input.dataset.field === 'raise_rate' ? Number(input.value) / 100 : input.value;
  try {
    await api(`/api/salary-projection/scenarios/${model.selected_scenario_id}/people/${person.id}/years/${year}`, {method: 'PUT', body: JSON.stringify(payload)});
    showMessage(`${year} override saved.`);
    await loadProjection();
  } catch (error) { showMessage(error.message, true); }
});

if (elements.table) loadProjection().catch((error) => showMessage(error.message, true));
