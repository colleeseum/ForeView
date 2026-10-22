// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {escapeHtml, htmlWithLanguageSpans, languageSpan} from '../shared/html.mjs';
import {t, locale} from '../shared/i18n.mjs';
import {formatMoneyDollars, formatDisplayDate} from '../shared/locale-format.mjs';
import {incomeSourceLabel} from '../shared/income-source-label.mjs';
import {createIncomeDialog} from './income-dialog.mjs';
import {
  configureIncomeCorrections,
  correctionPresentation,
  incomeConceptHasLocalizedLabel,
  incomeConceptLabel,
  initializeIncomeCorrections,
  openIncomeCorrection,
} from './income-corrections.mjs?v=20261022-1';

const elements = {
  tabs: document.querySelector('#income-tabs'),
  summary: document.querySelector('#income-summary'),
  message: document.querySelector('#income-message'),
  history: document.querySelector('#income-history'),
  taxReturns: document.querySelector('#income-tax-returns'),
  assessments: document.querySelector('#income-assessments'),
  rooms: document.querySelector('#income-rooms'),
  pension: document.querySelector('#income-pension'),
  normalized: document.querySelector('#income-normalized'),
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
let selectedSnapshotYear = null;
let latestSnapshotYear = null;
let pendingImport = null;
let pendingTaxReturn = null;
const defaultTaxYear = elements.form.elements.tax_year.value;
const editor = createIncomeDialog(elements.editor, elements.add);
const importer = createIncomeDialog(elements.importDialog, elements.importButton);
let loadGeneration = 0;
const sourceSections = [elements.summary, elements.history, elements.taxReturns, elements.assessments, elements.rooms, elements.pension, elements.normalized];
document.querySelectorAll('.fv-income button').forEach(node => node.classList.add('fv-button'));
document.querySelectorAll('.fv-income .primary-action, .fv-income #income-correction-save').forEach(node => node.classList.add('fv-button--primary'));
document.querySelectorAll('.fv-income input, .fv-income select, .fv-income textarea').forEach(node => node.classList.add('fv-input'));

function dialogMessage(target, message, error = false, language = locale) {
  target.textContent = message;
  target.hidden = !message;
  target.lang = language;
  target.setAttribute('role', error ? 'alert' : 'status');
  target.classList.toggle('error', error);
}

function money(value) {
  return formatMoneyDollars(value ?? 0);
}

function showMessage(message, error = false, language = locale, html = false) {
  if (html) elements.message.innerHTML = message;
  else elements.message.textContent = message;
  elements.message.classList.toggle('error', error);
  elements.message.lang = language;
}

function showError(error) {
  showMessage(error.message, true, error.language || 'en-CA');
  const target = elements.editor.open ? document.querySelector('#income-editor-message')
    : elements.importDialog.open ? document.querySelector('#income-import-message') : null;
  if (target) dialogMessage(target, error.message, true, error.language || 'en-CA');
}

function selectedPerson() {
  return people.find((person) => person.id === selectedPersonId) || null;
}

function updateImportAction() {
  if (elements.importPreview && elements.importFile) {
    elements.importPreview.disabled = importer.busy || elements.importFile.files.length === 0;
  }
}

function resetImportReview() {
  pendingImport = null;
  elements.importReview.hidden = true;
  elements.importReview.innerHTML = '';
  elements.importConfirm.hidden = true;
  elements.importPreview.hidden = false;
  updateImportAction();
}

function setImportBusy(busy) {
  importer.setBusy(busy);
  if (elements.importProgress) elements.importProgress.hidden = !busy;
  if (elements.importFile) elements.importFile.disabled = busy;
  if (elements.importPreview) {
    elements.importPreview.disabled = busy || !elements.importFile?.files.length;
  }
}

function normalizedName(value) {
  return String(value || '').toLocaleLowerCase().replace(/[^\p{L}\p{N}]/gu, '');
}

const pensionContributionAssumptions = new Set(['continue', 'stop']);
const registeredPlanTypes = new Set(['RRSP', 'TFSA', 'FHSA', 'RESP']);
const taxDocumentKinds = new Set(['return', 'assessment', 'annual_record', 'correction']);

function pensionContributionAssumptionLabel(assumption) {
  return pensionContributionAssumptions.has(assumption)
    ? t(`income.pension_assumptions.${assumption}`)
    : assumption || '';
}

function registeredPlanLabel(planType) {
  return registeredPlanTypes.has(planType)
    ? t(`income.registered_plans.${planType.toLowerCase()}`)
    : planType || '';
}

function taxDocumentKindLabel(documentKind) {
  return taxDocumentKinds.has(documentKind)
    ? t(`income.document_kinds.${documentKind}`)
    : documentKind || '';
}

function taxConceptDescriptionHtml(value) {
  const sourceLabel = value.description ?? value.label ?? '';
  return incomeConceptHasLocalizedLabel(value.concept)
    ? escapeHtml(incomeConceptLabel({concept: value.concept, label: sourceLabel}))
    : languageSpan(sourceLabel);
}

async function json(response) {
  const result = await response.json();
  if (!response.ok) {
    const error = new Error(result.error || t('income.request_failed'));
    error.status = response.status;
    error.language = result.error ? (result.error_language || 'en-CA') : locale;
    throw error;
  }
  return result;
}

function renderTabs() {
  elements.tabs.innerHTML = people.map((person) =>
    `<button class="view-tab fv-button${person.id === selectedPersonId ? ' active' : ''}" type="button" aria-pressed="${person.id === selectedPersonId}" data-person-id="${person.id}">${escapeHtml(person.name)}</button>`
  ).join('');
}

function renderHistory() {
  if (!records.length) {
    elements.history.innerHTML = `<p class="empty-panel">${t('income.no_history')}</p>`;
    return;
  }
  const body = records.map((record, index) => `<tr>
    <th>${record.year}${index === 0 ? ` <span class="latest-record">${t('income.latest')}</span>` : ''}</th>
    <td>${escapeHtml(record.province_of_residence || '—')}</td>
    <td>${money(record.employment_income)}</td><td>${money(record.bonus)}</td>
    <td><strong>${money(record.salary_rate)}</strong></td><td>${money(record.other_income)}</td>
    <td>${money(record.interest_income)}</td>
    <td>${money(record.gross_income)}</td><td>${money(record.cpp_qpp)}</td>
    <td>${money(record.ei)}</td><td>${money(record.qpip)}</td>
    <td>${money(record.rrsp_contribution)}</td><td>${money(record.rrsp_deduction)}</td>
    <td>${money(record.federal_tax)}</td><td>${money(record.provincial_tax)}</td>
    <td><strong>${money(record.disposable_income)}</strong></td>
    <td>${escapeHtml(incomeSourceLabel(record.source))}</td>
    <td><button class="table-action" type="button" data-edit-year="${record.year}">${t('income.edit')}</button></td>
  </tr>`).join('');
  elements.history.innerHTML = `<div class="table-wrap"><table class="income-history-table">
    <thead><tr><th>${t('income.year')}</th><th>${t('income.residence')}</th><th>${t('income.employment')}</th><th>${t('income.bonus')}</th><th>${t('income.salary_rate')}</th>
    <th>${t('income.other_employment')}</th><th>${t('income.interest')}</th><th>${t('income.employment_gross')}</th><th>${t('financial.cpp_qpp')}</th><th>${t('financial.ei')}</th><th>${t('financial.qpip')}</th>
    <th>${t('income.rrsp_contribution')}</th><th>${t('income.rrsp_deduction')}</th><th>${t('income.federal_tax')}</th>
    <th>${t('income.provincial_tax')}</th><th>${t('income.disposable')}</th><th>${t('income.source')}</th><th></th></tr></thead>
    <tbody>${body}</tbody></table></div>`;
}

function sourceNote(value) {
  const details = [
    incomeSourceLabel(value.source),
    value.document_kind === 'assessment' ? t('income.assessed') : value.document_kind === 'return' ? t('income.filed_return') : t('income.annual_record'),
    value.jurisdiction,
    value.line_code ? t('income.line', {code: value.line_code}) : null,
  ].filter(Boolean);
  return details.map(escapeHtml).join(' · ');
}

function renderSummary(snapshot, rooms) {
  if (!snapshot) {
    elements.summary.innerHTML = `<section class="income-summary-panel"><h2 class="income-summary-heading">${t('income.snapshot')}</h2><p class="empty-panel">${t('income.no_facts')}</p></section>`;
    return;
  }
  const optionalIncome = new Set([
    'oas_income', 'cpp_qpp_benefits', 'other_pension_income', 'interest_investment_income',
  ]);
  const yearOptions = snapshot.available_years.map((year) =>
    `<option value="${year}"${year === snapshot.tax_year ? ' selected' : ''}>${year}</option>`
  ).join('');
  const cards = snapshot.values
    .filter((value) => correctionPresentation(value.concept) || !optionalIncome.has(value.concept) || Number(value.amount) !== 0)
    .map((value) => {
      const presentation = correctionPresentation(value.concept);
      const correction = presentation?.correction;
      const underlying = correction?.current_underlying;
      const note = correction
        ? `${t('income.user_correction')} · ${t('income.underlying')}: ${sourceNote(underlying)}`
        : sourceNote(value);
      return `<div class="income-summary-value${presentation ? ' corrected' : ''}${presentation?.reviewRequired ? ' review-required' : ''}">
      <span class="income-summary-label">${taxConceptDescriptionHtml(value)}</span>
      <strong class="income-summary-amount">${money(value.amount)}</strong>
      ${presentation ? `<span class="income-correction-badge">${escapeHtml(presentation.badge)}</span>` : ''}
      <small class="income-summary-note">${note}</small>
      <button class="income-correction-action" type="button" data-correct-concept="${escapeHtml(value.concept)}">${presentation ? escapeHtml(presentation.action) : t('income.correct')}</button>
    </div>`;
    });
  const latestRooms = new Map();
  for (const room of rooms || []) {
    if (!latestRooms.has(room.plan_type)) latestRooms.set(room.plan_type, room);
  }
  for (const room of latestRooms.values()) {
    cards.push(`<div class="income-summary-value income-summary-room">
      <span class="income-summary-label">${escapeHtml(t('income.available_room', {plan: registeredPlanLabel(room.plan_type)}))}</span>
      <strong class="income-summary-amount">${money(room.available_room)}</strong>
      <small class="income-summary-note">${room.effective_year} · ${escapeHtml(room.source)}</small>
    </div>`);
  }
  elements.summary.innerHTML = `<section class="income-summary-panel">
    <div class="income-summary-heading">
      <div>
        <p class="eyebrow">${t(selectedSnapshotYear ? 'income.historical_snapshot' : 'income.latest_snapshot')}</p>
        <h2 class="income-summary-title">${t('income.tax_year', {year: snapshot.tax_year})}</h2>
      </div>
      <label class="income-year-filter">${t('income.view_tax_year')}<select data-income-snapshot-year>${yearOptions}</select></label>
      <p class="income-summary-note">${t('income.precedence_note')}</p>
    </div>
    <div class="income-summary-grid">${cards.join('')}</div>
  </section>`;
}

function renderSupplementary(assessments, rooms, pension, taxValues) {
  const roomRows = rooms.map((item) => `<tr>
    <td>${escapeHtml(registeredPlanLabel(item.plan_type))}</td><td>${item.effective_year}</td><td>${money(item.available_room)}</td>
    <td>${money(item.deduction_limit)}</td><td>${money(item.unused_contributions)}</td>
    <td>${escapeHtml(formatDisplayDate(item.as_of_date))}</td><td>${escapeHtml(item.source)}</td>
  </tr>`).join('');

  const pensionEstimates = pension?.estimates?.map((item) => `<tr>
    <td>${escapeHtml(pensionContributionAssumptionLabel(item.contribution_assumption))}</td><td>${item.activation_age}</td>
    <td>${money(item.monthly_amount)}</td>
  </tr>`).join('') || '';

  const pensionEarnings = pension?.earnings?.map((item) => `<tr>
    <td>${item.year}</td><td>${money(item.qpp_earnings)}</td><td>${money(item.cpp_earnings)}</td>
    <td>${escapeHtml(item.status || '')}</td>
  </tr>`).join('') || '';

  const taxHistoryRows = taxValues
    .filter((value) => value.document_kind === 'return')
    .map((item) => `<tr class="tax-history-row">
      <td>${item.tax_year}</td><td>${escapeHtml(taxDocumentKindLabel(item.document_kind))}</td>
      <td>${escapeHtml(item.jurisdiction)}</td><td>${item.effective_year}</td>
      <td>${escapeHtml(item.line_code || '—')}</td><td>${taxConceptDescriptionHtml(item)}</td>
      <td>${item.reported_amount === null ? '—' : money(item.reported_amount)}</td>
      <td>${item.determined_amount === null ? '—' : money(item.determined_amount)}</td>
      <td>${escapeHtml(item.source)}</td>
    </tr>`).join('');

  const assessmentRowsFull = assessments.map((item) => `<tr>
    <td>${item.year}</td><td>${escapeHtml(item.jurisdiction)}</td><td>${escapeHtml(formatDisplayDate(item.issued_on))}</td>
    <td>${money(item.total_income)}</td><td>${money(item.net_income)}</td><td>${money(item.taxable_income)}</td>
    <td>${money(item.net_tax)}</td><td>${money(item.additional_contributions)}</td>
    <td>${money(item.tax_withheld)}</td><td>${money(item.balance)}</td><td>${escapeHtml(item.source)}</td>
  </tr>`).join('');

  const normalizedRows = taxValues
    .filter((value) => value.document_kind !== 'return')
    .map((item) => `<tr class="normalized-row">
      <td>${item.tax_year}</td><td>${escapeHtml(taxDocumentKindLabel(item.document_kind))}</td>
      <td>${escapeHtml(item.jurisdiction)}</td><td>${item.effective_year}</td>
      <td>${escapeHtml(item.line_code || '—')}</td><td>${taxConceptDescriptionHtml(item)}</td>
      <td>${item.reported_amount === null ? '—' : money(item.reported_amount)}</td>
      <td>${item.determined_amount === null ? '—' : money(item.determined_amount)}</td>
      <td>${escapeHtml(item.source)}</td>
    </tr>`).join('');

  elements.taxReturns.innerHTML = taxHistoryRows
    ? `<div class="table-wrap"><table class="income-history-table">
      <thead><tr>${taxValueHeadings()}</tr></thead>
      <tbody>${taxHistoryRows}</tbody></table></div>`
    : `<p class="empty-panel">${t('income.no_tax_returns')}</p>`;

  elements.assessments.innerHTML = assessmentRowsFull
    ? `<div class="table-wrap"><table class="income-assessments-table">
      <thead><tr><th>${t('income.year')}</th><th>${t('income.jurisdiction')}</th><th>${t('income.issued')}</th><th>${t('income.total')}</th><th>${t('income.net')}</th><th>${t('income.taxable')}</th><th>${t('income.net_tax')}</th><th>${t('income.other')}</th><th>${t('income.withheld')}</th><th>${t('income.balance')}</th><th>${t('income.source')}</th></tr></thead>
      <tbody>${assessmentRowsFull}</tbody></table></div>`
    : `<p class="empty-panel">${t('income.no_assessments')}</p>`;

  elements.rooms.innerHTML = roomRows
    ? `<div class="table-wrap"><table class="income-rooms-table">
      <thead><tr><th>${t('income.plan')}</th><th>${t('income.effective_year')}</th><th>${t('income.available')}</th><th>${t('income.limit')}</th><th>${t('income.unused')}</th><th>${t('income.as_of')}</th><th>${t('income.source')}</th></tr></thead>
      <tbody>${roomRows}</tbody></table></div>`
    : `<p class="empty-panel">${t('income.no_rooms')}</p>`;

  elements.pension.innerHTML = pension
    ? `<div class="pension-details">
         <div class="table-wrap"><table class="income-pension-table">
           <thead><tr><th>${t('income.assumption')}</th><th>${t('income.age')}</th><th>${t('income.monthly')}</th></tr></thead>
           <tbody>${pensionEstimates}</tbody>
         </table></div>
         <div class="table-wrap"><table class="income-pension-earnings-table">
           <thead><tr><th>${t('income.year')}</th><th>${t('financial.qpp')}</th><th>${t('financial.cpp')}</th><th>${t('income.status')}</th></tr></thead>
           <tbody>${pensionEarnings}</tbody>
         </table></div>
       </div>`
    : `<p class="empty-panel">${t('income.no_pension')}</p>`;

  elements.normalized.innerHTML = normalizedRows
    ? `<div class="table-wrap"><table class="income-normalized-table">
      <thead><tr>${taxValueHeadings()}</tr></thead>
      <tbody>${normalizedRows}</tbody></table></div>`
    : `<p class="empty-panel">${t('income.no_normalized')}</p>`;
}

function taxValueHeadings() {
  return [
    'year', 'document_short', 'jurisdiction', 'effective_year', 'line_heading',
    'concept', 'reported', 'determined', 'source',
  ].map((key) => `<th>${t(`income.${key}`)}</th>`).join('');
}

function updateSalaryRate() {
  const income = Number(elements.form.elements.employment_income.value || 0);
  const bonus = Number(elements.form.elements.bonus.value || 0);
  elements.salaryRate.textContent = money(Math.max(0, income - bonus));
}

function fillForm(record = {}) {
  for (const name of [
    'employment_income', 'bonus', 'other_income', 'interest_income', 'cpp_qpp', 'ei', 'qpip',
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
    elements.editorPerson.textContent = personName ? t('income.person', {name: personName}) : '';
  }
  dialogMessage(document.querySelector('#income-editor-message'), '');
  editor.open();
}

async function load() {
  const generation = ++loadGeneration;
  elements.add.disabled = true;
  elements.importButton.disabled = true;
  const failure = document.querySelector('#income-load-error');
  const retry = document.querySelector('#income-retry');
  failure.hidden = true;
  retry.hidden = true;
  for (const section of sourceSections) {
    section.replaceChildren();
    section.setAttribute('aria-busy', 'true');
  }
  try {
    if (!selectedPersonId) {
      const result = await fetch('/api/model/people').then(json);
      if (generation !== loadGeneration) return false;
      people = result.people;
      selectedPersonId = people[0]?.id || null;
    }
    renderTabs();
    if (!selectedPersonId) {
      showMessage(t('income.add_person_first'), true);
      records = [];
      renderHistory();
      return false;
    }
    const yearQuery = selectedSnapshotYear ? `&year=${selectedSnapshotYear}` : '';
    const result = await fetch(`/api/income?person_id=${selectedPersonId}${yearQuery}`).then(json);
    if (generation !== loadGeneration) return false;
    if (!selectedSnapshotYear) records = result.records;
    latestSnapshotYear = result.snapshot?.available_years?.[0] || null;
    configureIncomeCorrections({
      personId: selectedPersonId,
      personName: selectedPerson()?.name,
      snapshot: result.snapshot,
      corrections: result.corrections || [],
    });
    renderSummary(result.snapshot, selectedSnapshotYear ? [] : result.registered_rooms || []);
    renderHistory();
    renderSupplementary(
      result.assessments || [], result.registered_rooms || [], result.public_pension,
      result.tax_values || [],
    );
    showMessage(records.length
      ? t(records.length === 1 ? 'income.record_count' : 'income.record_count_plural', {count: records.length})
      : t('income.no_employment_records'));
    decorateTables();
    elements.add.disabled = false;
    elements.importButton.disabled = false;
    return true;
  } catch (error) {
    if (generation !== loadGeneration) return false;
    dialogMessage(failure, error.message, true, error.language || 'en-CA');
    retry.hidden = false;
    return false;
  } finally {
    if (generation === loadGeneration) {
      for (const section of sourceSections) section.setAttribute('aria-busy', 'false');
    }
  }
}

function decorateTables() {
  for (const container of [elements.history, elements.taxReturns, elements.assessments, elements.rooms, elements.pension, elements.normalized]) {
    container.querySelectorAll('table').forEach(table => {
      table.classList.add('fv-table');
      table.createCaption().textContent = container.closest('.income-record-section')?.querySelector('summary')?.textContent || t('income.source');
      table.querySelectorAll('thead th').forEach(cell => {cell.scope = 'col';});
      const region = table.parentElement;
      region.classList.add('fv-table-scroll');
      region.tabIndex = 0;
      region.setAttribute('role', 'region');
      region.setAttribute('aria-label', table.caption.textContent);
      region.setAttribute('aria-describedby', 'income-scroll-hint');
    });
  }
}
document.querySelector('#income-retry').addEventListener('click', load);

elements.tabs.addEventListener('click', (event) => {
  const tab = event.target.closest('[data-person-id]');
  if (!tab) return;
  selectedPersonId = Number(tab.dataset.personId);
  selectedSnapshotYear = null;
  load().catch(showError);
});
elements.summary.addEventListener('change', (event) => {
  const filter = event.target.closest('[data-income-snapshot-year]');
  if (!filter) return;
  const year = Number(filter.value);
  selectedSnapshotYear = year === latestSnapshotYear ? null : year;
  load().catch(showError);
});
elements.summary.addEventListener('click', (event) => {
  const button = event.target.closest('[data-correct-concept]');
  if (!button) return;
  openIncomeCorrection(button.dataset.correctConcept);
});
elements.history.addEventListener('click', (event) => {
  const button = event.target.closest('[data-edit-year]');
  if (!button) return;
  const record = records.find((item) => item.year === Number(button.dataset.editYear));
  if (record) {
    pendingTaxReturn = null;
    openEditor(record);
  }
});
elements.add.addEventListener('click', () => {
  pendingTaxReturn = null;
  openEditor();
});
elements.editorClose.addEventListener('click', () => editor.close());
elements.form.addEventListener('input', updateSalaryRate);
elements.importButton.addEventListener('click', () => {
  resetImportReview();
  dialogMessage(document.querySelector('#income-import-message'), '');
  importer.open();
});
elements.importClose.addEventListener('click', () => importer.close());
elements.importFile?.addEventListener('change', resetImportReview);
elements.importForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (importer.busy) return;
  const data = new FormData(elements.importForm);
  setImportBusy(true);
  dialogMessage(document.querySelector('#income-import-message'), t('income.analysing'));
  try {
    const preview = await fetch('/api/income/import/preview', {
      method: 'POST', body: data,
    }).then(json);
    if (preview.taxpayer_name) {
      const taxpayer = people.find(
        (person) => normalizedName(person.name) === normalizedName(preview.taxpayer_name),
      );
      if (!taxpayer) {
        const error = new Error(t('income.person_not_configured', {name: preview.taxpayer_name}));
        error.language = locale;
        throw error;
      }
      selectedPersonId = taxpayer.id;
      selectedSnapshotYear = null;
      await load();
    }
    if (preview.kind === 'tax_return') {
      setImportBusy(false);
      importer.close();
      elements.importForm.reset();
      updateImportAction();
      pendingTaxReturn = preview;
      openEditor(preview);
    } else {
      pendingImport = preview;
      elements.importReview.hidden = false;
      elements.importConfirm.hidden = false;
      elements.importPreview.hidden = true;
      if (preview.kind === 'tax_assessment') {
        const conceptCount = preview.tax_values?.length || 0;
        elements.importReview.innerHTML = `<h3>${languageSpan(preview.source_name)}</h3>
          <p>${escapeHtml(t('income.assessment_preview', {year: preview.tax_year, issued: formatDisplayDate(preview.issued_on), tax: money(preview.net_tax), balance: money(preview.balance)}))}</p>
          ${preview.rrsp_effective_year ? `<p>${escapeHtml(t('income.rrsp_room_preview', {year: preview.rrsp_effective_year, amount: money(preview.rrsp_available_room)}))}</p>` : ''}
          <p>${escapeHtml(t(conceptCount === 1 ? 'income.concept_retained' : 'income.concepts_retained', {count: conceptCount}))}</p>`;
      } else {
        const years = t(preview.earnings.length === 1 ? 'income.pension_year' : 'income.pension_years', {count: preview.earnings.length});
        const estimates = t(preview.estimates.length === 1 ? 'income.pension_estimate' : 'income.pension_estimates', {count: preview.estimates.length});
        elements.importReview.innerHTML = `<h3>${languageSpan(preview.source_name)}</h3>
          <p>${escapeHtml(t('income.pension_preview', {issued: formatDisplayDate(preview.issued_on), years, estimates}))}</p>
          ${preview.excludes_second_enhancement ? `<p><strong>${t('income.enhancement_excluded')}</strong></p>` : ''}`;
      }
    }
    const identity = preview.taxpayer_name
      ? t('income.pdf_taxpayer', {name: preview.taxpayer_name})
      : t('income.no_pdf_taxpayer');
    dialogMessage(document.querySelector('#income-import-message'), identity);
    const loaded = htmlWithLanguageSpans(
      ({source}) => t('income.loaded_for_review', {source}),
      {source: preview.source_name || 'T1'},
    );
    showMessage(`${escapeHtml(identity)} ${loaded}`, false, locale, true);
  } catch (error) {
    showError(error);
  } finally {
    setImportBusy(false);
  }
});
elements.importConfirm.addEventListener('click', async () => {
  if (!pendingImport || importer.busy) return;
  const endpoint = pendingImport.kind === 'tax_assessment'
    ? `/api/income/people/${selectedPersonId}/assessments`
    : `/api/income/people/${selectedPersonId}/public-pension-statements`;
  setImportBusy(true);
  dialogMessage(document.querySelector('#income-import-message'), t('income.saving'));
  try {
    await fetch(endpoint, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(pendingImport),
    }).then(json);
    const sourceName = pendingImport.source_name;
    pendingImport = null;
    elements.importForm.reset();
    await load();
    setImportBusy(false);
    importer.close();
    showMessage(
      htmlWithLanguageSpans(({source}) => t('income.source_saved', {source}), {source: sourceName}),
      false,
      locale,
      true,
    );
  } catch (error) { showError(error); }
  finally {setImportBusy(false);}
});
elements.form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (editor.busy) return;
  const values = Object.fromEntries(new FormData(elements.form));
  if (pendingTaxReturn) {
    values.tax_values = pendingTaxReturn.tax_values || [];
    values.source_version = pendingTaxReturn.source_version;
    values.document_hash = pendingTaxReturn.document_hash;
  }
  const year = Number(elements.form.elements.tax_year.value);
  editor.setBusy(true);
  dialogMessage(document.querySelector('#income-editor-message'), t('income.saving'));
  try {
    await fetch(
      `/api/income/people/${selectedPersonId}/years/${year}`,
      {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(values)},
    ).then(json);
    pendingTaxReturn = null;
    await load();
    editor.setBusy(false);
    editor.close();
    showMessage(t('income.annual_saved', {year}));
  } catch (error) { showError(error); }
  finally {editor.setBusy(false);}
});

initializeIncomeCorrections({
  requestJson: (url, options) => fetch(url, options).then(json),
  reload: load,
  notify: showMessage,
  money,
});
load().catch(showError);
