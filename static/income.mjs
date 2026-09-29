import {escapeHtml} from './html.mjs';

const elements = {
  tabs: document.querySelector('#income-tabs'),
  message: document.querySelector('#income-message'),
  history: document.querySelector('#income-history'),
  supplementary: document.querySelector('#income-supplementary'),
  add: document.querySelector('#income-add'),
  form: document.querySelector('#income-form'),
  editor: document.querySelector('#income-dialog-backdrop'),
  editorClose: document.querySelector('#income-dialog-close'),
  editorPerson: document.querySelector('#income-editor-person'),
  importButton: document.querySelector('#income-import'),
  importDialog: document.querySelector('#ufile-dialog-backdrop'),
  importClose: document.querySelector('#ufile-dialog-close'),
  importForm: document.querySelector('#ufile-form'),
  importFile: document.querySelector('#income-import-file'),
  importPreview: document.querySelector('#income-import-preview'),
  importProgress: document.querySelector('#income-import-progress'),
  importReview: document.querySelector('#income-import-review'),
  importConfirm: document.querySelector('#income-import-confirm'),
  salaryRate: document.querySelector('#income-salary-rate'),
};

let people = [];
let records = [];
let selectedPersonId = null;
let pendingImport = null;
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

function selectedPerson() {
  return people.find((person) => person.id === selectedPersonId) || null;
}

function updateImportAction() {
  if (elements.importPreview && elements.importFile) {
    elements.importPreview.disabled = elements.importFile.files.length === 0;
  }
}

function setImportBusy(busy) {
  if (elements.importProgress) elements.importProgress.hidden = !busy;
  if (elements.importFile) elements.importFile.disabled = busy;
  if (elements.importPreview) {
    elements.importPreview.disabled = busy || !elements.importFile?.files.length;
  }
}

function normalizedName(value) {
  return String(value || '').toLocaleLowerCase().replace(/[^\p{L}\p{N}]/gu, '');
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
    <td>${escapeHtml(record.province_of_residence || '—')}</td>
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
    <thead><tr><th>Year</th><th>Residence</th><th>Employment income</th><th>Bonus</th><th>Salary rate</th>
    <th>Other employment income</th><th>Gross</th><th>CPP/QPP</th><th>EI</th><th>QPIP</th>
    <th>RRSP contribution</th><th>RRSP deduction</th><th>Federal tax</th>
    <th>Provincial tax</th><th>Disposable</th><th>Source</th><th></th></tr></thead>
    <tbody>${body}</tbody></table></div>`;
}

function renderSupplementary(assessments, rooms, pension) {
  const assessmentRows = assessments.map((item) => `<tr>
    <td>${item.year}</td><td>${escapeHtml(item.jurisdiction)}</td><td>${escapeHtml(item.issued_on)}</td>
    <td>${money(item.total_income)}</td><td>${money(item.net_income)}</td><td>${money(item.taxable_income)}</td>
    <td>${money(item.net_tax)}</td><td>${money(item.additional_contributions)}</td>
    <td>${money(item.tax_withheld)}</td><td>${money(item.balance)}</td><td>${escapeHtml(item.source)}</td>
  </tr>`).join('');
  const roomRows = rooms.map((item) => `<tr>
    <td>${escapeHtml(item.plan_type)}</td><td>${item.effective_year}</td><td>${money(item.available_room)}</td>
    <td>${money(item.deduction_limit)}</td><td>${money(item.unused_contributions)}</td>
    <td>${escapeHtml(item.as_of_date)}</td><td>${escapeHtml(item.source)}</td>
  </tr>`).join('');
  const pensionEstimates = pension?.estimates?.map((item) => `<tr>
    <td>${escapeHtml(item.contribution_assumption)}</td><td>${item.activation_age}</td>
    <td>${money(item.monthly_amount)}</td>
  </tr>`).join('') || '';
  const pensionEarnings = pension?.earnings?.map((item) => `<tr>
    <td>${item.year}</td><td>${money(item.qpp_earnings)}</td><td>${money(item.cpp_earnings)}</td>
    <td>${escapeHtml(item.status || '')}</td>
  </tr>`).join('') || '';
  elements.supplementary.innerHTML = `
    <section class="income-record-section"><h2>Tax assessments</h2>${assessmentRows
      ? `<div class="table-wrap"><table><thead><tr><th>Year</th><th>Jurisdiction</th><th>Issued</th><th>Total income</th><th>Net income</th><th>Taxable income</th><th>Net tax</th><th>Other contributions</th><th>Tax withheld</th><th>Balance</th><th>Source</th></tr></thead><tbody>${assessmentRows}</tbody></table></div>`
      : '<p class="empty-panel">No assessment notices loaded.</p>'}</section>
    <section class="income-record-section"><h2>Registered-plan room</h2>${roomRows
      ? `<div class="table-wrap"><table><thead><tr><th>Plan</th><th>Effective year</th><th>Available room</th><th>Deduction limit</th><th>Unused contributions</th><th>As of</th><th>Source</th></tr></thead><tbody>${roomRows}</tbody></table></div>`
      : '<p class="empty-panel">No contribution-room snapshots loaded.</p>'}</section>
    <section class="income-record-section"><h2>Public pension</h2>${pension
      ? `<p>${escapeHtml(pension.provider)} statement issued ${escapeHtml(pension.issued_on)}.${pension.excludes_second_enhancement ? ' <strong>Estimate excludes the second enhancement component.</strong>' : ''}</p>
         <div class="table-wrap"><table><thead><tr><th>Contribution assumption</th><th>Start age</th><th>Monthly estimate</th></tr></thead><tbody>${pensionEstimates}</tbody></table></div>
         <details><summary>Pensionable earnings history</summary><div class="table-wrap"><table><thead><tr><th>Year</th><th>QPP</th><th>CPP</th><th>Status</th></tr></thead><tbody>${pensionEarnings}</tbody></table></div></details>`
      : '<p class="empty-panel">No CPP/QPP participation statement loaded.</p>'}</section>`;
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
  elements.form.elements.province_of_residence.value = record.province_of_residence || '';
  elements.form.elements.payroll_plan.value = record.payroll_plan || '';
  const source = ['T1', 'UFile T1', 'Manual'].includes(record.source) ? record.source : 'T1';
  elements.form.elements.source.value = source;
  updateSalaryRate();
}

function openEditor(record = {}) {
  fillForm(record);
  if (elements.editorPerson) {
    const personName = record.taxpayer_name || selectedPerson()?.name;
    elements.editorPerson.textContent = personName ? `Person: ${personName}` : '';
  }
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
  renderSupplementary(result.assessments || [], result.registered_rooms || [], result.public_pension);
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
elements.importButton.addEventListener('click', () => {
  pendingImport = null;
  elements.importReview.hidden = true;
  elements.importReview.innerHTML = '';
  elements.importConfirm.hidden = true;
  updateImportAction();
  elements.importDialog.hidden = false;
});
elements.importClose.addEventListener('click', () => { elements.importDialog.hidden = true; });
elements.importFile?.addEventListener('change', updateImportAction);
elements.importForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const data = new FormData(elements.importForm);
  setImportBusy(true);
  try {
    const preview = await fetch('/api/income/import/preview', {
      method: 'POST', body: data,
    }).then(json);
    if (preview.taxpayer_name) {
      const taxpayer = people.find(
        (person) => normalizedName(person.name) === normalizedName(preview.taxpayer_name),
      );
      if (!taxpayer) {
        throw new Error(`This PDF is for ${preview.taxpayer_name}, but that person is not configured. Nothing was loaded.`);
      }
      selectedPersonId = taxpayer.id;
      renderTabs();
    }
    if (preview.kind === 'tax_return') {
      elements.importDialog.hidden = true;
      elements.importForm.reset();
      updateImportAction();
      openEditor(preview);
    } else {
      pendingImport = preview;
      elements.importReview.hidden = false;
      elements.importConfirm.hidden = false;
      if (preview.kind === 'tax_assessment') {
        elements.importReview.innerHTML = `<h3>${escapeHtml(preview.source_name)}</h3>
          <p>${preview.tax_year}, issued ${escapeHtml(preview.issued_on)}. Net tax ${money(preview.net_tax)}; balance ${money(preview.balance)}.</p>
          ${preview.rrsp_effective_year ? `<p>RRSP room for ${preview.rrsp_effective_year}: <strong>${money(preview.rrsp_available_room)}</strong>.</p>` : ''}`;
      } else {
        elements.importReview.innerHTML = `<h3>${escapeHtml(preview.source_name)}</h3>
          <p>Issued ${escapeHtml(preview.issued_on)} with ${preview.earnings.length} years of pensionable earnings and ${preview.estimates.length} estimates.</p>
          ${preview.excludes_second_enhancement ? '<p><strong>The official estimates exclude the second enhancement component.</strong></p>' : ''}`;
      }
    }
    const identity = preview.taxpayer_name
      ? `PDF taxpayer: ${preview.taxpayer_name}. `
      : 'The PDF did not expose a taxpayer name. Verify the document before saving. ';
    showMessage(`${identity}${preview.source_name || 'T1'} values loaded for review. Enter any bonus, verify the values, then save.`);
  } catch (error) {
    showMessage(error.message, true);
  } finally {
    setImportBusy(false);
  }
});
elements.importConfirm.addEventListener('click', async () => {
  if (!pendingImport) return;
  const endpoint = pendingImport.kind === 'tax_assessment'
    ? `/api/income/people/${selectedPersonId}/assessments`
    : `/api/income/people/${selectedPersonId}/public-pension-statements`;
  try {
    await fetch(endpoint, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(pendingImport),
    }).then(json);
    const sourceName = pendingImport.source_name;
    pendingImport = null;
    elements.importDialog.hidden = true;
    elements.importForm.reset();
    updateImportAction();
    showMessage(`${sourceName} saved.`);
    await load();
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
