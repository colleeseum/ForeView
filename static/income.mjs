import {escapeHtml} from './html.mjs';

const elements = {
  tabs: document.querySelector('#income-tabs'),
  message: document.querySelector('#income-message'),
  history: document.querySelector('#income-history'),
  add: document.querySelector('#income-add'),
  form: document.querySelector('#income-form'),
  editor: document.querySelector('#income-dialog-backdrop'),
  editorClose: document.querySelector('#income-dialog-close'),
  importButton: document.querySelector('#income-import'),
  importDialog: document.querySelector('#ufile-dialog-backdrop'),
  importClose: document.querySelector('#ufile-dialog-close'),
  importForm: document.querySelector('#ufile-form'),
  salaryRate: document.querySelector('#income-salary-rate'),
};

let people = [];
let records = [];
let selectedPersonId = null;
const defaultTaxYear = elements.form.elements.tax_year.value;

function money(value) {
  return Number(value || 0).toLocaleString('en-CA', {
    style: 'currency', currency: 'CAD', minimumFractionDigits: 2,
  });
}

function showMessage(message, error = false) {
  elements.message.textContent = message;
  elements.message.classList.toggle('error', error);
}

async function json(response) {
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Request failed');
  return result;
}

function renderTabs() {
  elements.tabs.innerHTML = people.map((person) =>
    `<button class="view-tab${person.id === selectedPersonId ? ' active' : ''}" type="button" data-person-id="${person.id}">${escapeHtml(person.name)}</button>`
  ).join('');
}

function renderHistory() {
  if (!records.length) {
    elements.history.innerHTML = '<p class="empty-panel">No annual employment records yet.</p>';
    return;
  }
  const body = records.map((record, index) => `<tr>
    <th>${record.year}${index === 0 ? ' <span class="latest-record">Latest</span>' : ''}</th>
    <td>${money(record.employment_income)}</td><td>${money(record.bonus)}</td>
    <td><strong>${money(record.salary_rate)}</strong></td><td>${money(record.other_income)}</td>
    <td>${money(record.gross_income)}</td><td>${money(record.cpp_qpp)}</td>
    <td>${money(record.ei)}</td><td>${money(record.qpip)}</td>
    <td>${money(record.rrsp_contribution)}</td><td>${money(record.rrsp_deduction)}</td>
    <td>${money(record.federal_tax)}</td><td>${money(record.provincial_tax)}</td>
    <td><strong>${money(record.disposable_income)}</strong></td>
    <td>${escapeHtml(record.source)}</td>
    <td><button class="table-action" type="button" data-edit-year="${record.year}">Edit</button></td>
  </tr>`).join('');
  elements.history.innerHTML = `<div class="table-wrap"><table class="income-history-table">
    <thead><tr><th>Year</th><th>Employment income</th><th>Bonus</th><th>Salary rate</th>
    <th>Other income</th><th>Gross</th><th>CPP/QPP</th><th>EI</th><th>QPIP</th>
    <th>RRSP contribution</th><th>RRSP deduction</th><th>Federal tax</th>
    <th>Provincial tax</th><th>Disposable</th><th>Source</th><th></th></tr></thead>
    <tbody>${body}</tbody></table></div>`;
}

function updateSalaryRate() {
  const income = Number(elements.form.elements.employment_income.value || 0);
  const bonus = Number(elements.form.elements.bonus.value || 0);
  elements.salaryRate.textContent = money(Math.max(0, income - bonus));
}

function fillForm(record = {}) {
  for (const name of [
    'employment_income', 'bonus', 'other_income', 'cpp_qpp', 'ei', 'qpip',
    'rrsp_contribution', 'rrsp_deduction', 'federal_tax', 'provincial_tax',
  ]) elements.form.elements[name].value = record[name] || '0';
  elements.form.elements.tax_year.value = record.year || defaultTaxYear;
  elements.form.elements.tax_year.disabled = Boolean(record.id);
  const source = ['T1', 'UFile T1', 'Manual'].includes(record.source) ? record.source : 'T1';
  elements.form.elements.source.value = source;
  updateSalaryRate();
}

function openEditor(record = {}) {
  fillForm(record);
  elements.editor.hidden = false;
}

async function load() {
  if (!selectedPersonId) {
    const result = await fetch('/api/model/people').then(json);
    people = result.people;
    selectedPersonId = people[0]?.id || null;
  }
  renderTabs();
  if (!selectedPersonId) {
    showMessage('Add a person in Setup before recording income.', true);
    elements.add.disabled = true;
    elements.importButton.disabled = true;
    records = [];
    renderHistory();
    return;
  }
  const result = await fetch(`/api/income?person_id=${selectedPersonId}`).then(json);
  records = result.records;
  renderHistory();
  showMessage(records.length
    ? `${records.length} annual record${records.length === 1 ? '' : 's'}, newest first.`
    : 'No annual employment records have been saved.');
}

elements.tabs.addEventListener('click', (event) => {
  const tab = event.target.closest('[data-person-id]');
  if (!tab) return;
  selectedPersonId = Number(tab.dataset.personId);
  load().catch((error) => showMessage(error.message, true));
});
elements.history.addEventListener('click', (event) => {
  const button = event.target.closest('[data-edit-year]');
  if (!button) return;
  const record = records.find((item) => item.year === Number(button.dataset.editYear));
  if (record) openEditor(record);
});
elements.add.addEventListener('click', () => openEditor());
elements.editorClose.addEventListener('click', () => { elements.editor.hidden = true; });
elements.form.addEventListener('input', updateSalaryRate);
elements.importButton.addEventListener('click', () => { elements.importDialog.hidden = false; });
elements.importClose.addEventListener('click', () => { elements.importDialog.hidden = true; });
elements.importForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const data = new FormData(elements.importForm);
  try {
    const preview = await fetch('/api/income/import/ufile/preview', {
      method: 'POST', body: data,
    }).then(json);
    elements.importDialog.hidden = true;
    elements.importForm.reset();
    openEditor(preview);
    showMessage('UFile values loaded for review. Enter any bonus, verify the values, then save.');
  } catch (error) { showMessage(error.message, true); }
});
elements.form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(elements.form));
  const year = Number(elements.form.elements.tax_year.value);
  try {
    await fetch(
      `/api/income/people/${selectedPersonId}/years/${year}`,
      {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(values)},
    ).then(json);
    elements.editor.hidden = true;
    showMessage(`${year} annual employment record saved.`);
    await load();
  } catch (error) { showMessage(error.message, true); }
});

load().catch((error) => showMessage(error.message, true));
