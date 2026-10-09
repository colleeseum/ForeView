// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {formSignature} from './form-state.mjs';
import {escapeHtml, htmlWithLanguageSpans} from './html.mjs';
import {t, locale} from './i18n.mjs';
import {incomeSourceLabel} from './income-source-label.mjs';

let elements = null;

let personId = null;
let personName = '';
let snapshot = null;
let corrections = new Map();
let activeValue = null;
let activeCorrection = null;
let streamRevision = 0;
let baseline = '';
let requestJson = null;
let reload = null;
let notify = null;
let formatMoney = null;

const LOCALIZED_CONCEPTS = new Set([
  'employment_income',
  'oas_income',
  'cpp_qpp_benefits',
  'other_pension_income',
  'interest_investment_income',
  'total_income',
  'taxable_income',
  'rrsp_deduction',
  'net_federal_tax',
  'provincial_income_tax',
]);

const LOCALIZED_DOCUMENT_KINDS = new Set([
  'return',
  'assessment',
  'annual_record',
  'correction',
]);

export function incomeConceptLabel(value) {
  return incomeConceptHasLocalizedLabel(value.concept)
    ? t(`income.concepts.${value.concept}`)
    : value.label;
}

export function incomeConceptHasLocalizedLabel(concept) {
  return LOCALIZED_CONCEPTS.has(concept);
}

function conceptMessage(key, value) {
  const label = incomeConceptLabel(value);
  return incomeConceptHasLocalizedLabel(value.concept)
    ? escapeHtml(t(key, {label}))
    : htmlWithLanguageSpans(({label: token}) => t(key, {label: token}), {label});
}

function sourceDetails(source) {
  return [
    incomeSourceLabel(source?.source),
    LOCALIZED_DOCUMENT_KINDS.has(source?.document_kind)
      ? t(`income.document_kinds.${source.document_kind}`)
      : source?.document_kind,
    source?.jurisdiction,
    source?.line_code ? t('income_corrections.line', {code: source.line_code}) : null,
    source?.source_version ? t('income_corrections.version', {version: source.source_version}) : null,
    source?.document_hash ? t('income_corrections.document', {hash: source.document_hash}) : null,
  ].filter(Boolean).join(' · ');
}

function valueSource(value) {
  return {
    amount: value.amount,
    source: value.source,
    document_kind: value.document_kind,
    jurisdiction: value.jurisdiction,
    line_code: value.line_code,
    source_version: value.source_version,
    document_hash: value.document_hash,
  };
}

function showSource(amountElement, noteElement, source) {
  amountElement.textContent = source?.amount == null ? t('income_corrections.no_value') : formatMoney(source.amount);
  noteElement.textContent = sourceDetails(source) || t('income_corrections.no_provenance');
}

function signature() {
  return formSignature(elements.form);
}

function updateSaveButton() {
  const amount = elements.form.elements.correct_amount.value;
  const reason = elements.form.elements.reason.value.trim();
  elements.save.disabled = !amount || !reason || signature() === baseline;
}

function setBusy(busy) {
  for (const button of [elements.save, elements.remove, elements.confirm]) {
    button.disabled = busy;
  }
  if (!busy) updateSaveButton();
}

function showDialogMessage(message, error = false, language = locale) {
  elements.message.textContent = message;
  elements.message.classList.toggle('error', error);
  elements.message.lang = language;
}

function revisionLabel(kind) {
  return t(`income_corrections.revision_${kind}`);
}

function renderHistory(revisions) {
  if (!revisions.length) {
    elements.history.innerHTML = `<p class="field-note">${t('income_corrections.no_revisions')}</p>`;
    elements.historyPanel.open = false;
    return;
  }
  elements.history.innerHTML = revisions.slice().reverse().map((revision) => `
    <article class="income-correction-revision">
      <div><strong>${t('income_corrections.revision', {number: revision.revision_number})}</strong><span>${escapeHtml(revisionLabel(revision.revision_kind))}</span><time>${escapeHtml(revision.created_at)}</time></div>
      <p>${revision.correct_amount == null ? t('income_corrections.no_effective') : formatMoney(revision.correct_amount)} · ${escapeHtml(revision.reason)}</p>
      <small>${escapeHtml(t('income_corrections.source_reviewed', {
        amount: revision.source_at_correction.amount == null ? t('income_corrections.none') : formatMoney(revision.source_at_correction.amount),
        provenance: sourceDetails(revision.source_at_correction) || t('income_corrections.no_provenance_short'),
      }))}</small>
    </article>`).join('');
}

async function loadHistory() {
  const result = await requestJson(
    `/api/income/corrections/person/${personId}/year/${snapshot.tax_year}/${encodeURIComponent(activeValue.concept)}`,
  );
  const revisions = result.corrections || [];
  const latest = revisions.at(-1);
  if (!activeCorrection && latest?.revision_kind === 'remove') {
    streamRevision = latest.revision_number;
  }
  renderHistory(revisions);
}

function closeDialog() {
  elements.dialog.hidden = true;
  activeValue = null;
  activeCorrection = null;
}

export function correctionPresentation(concept) {
  const correction = corrections.get(concept);
  if (!correction) return null;
  return {
    corrected: true,
    reviewRequired: correction.review_required,
    badge: correction.review_required ? t('income_corrections.review_required_badge') : t('income_corrections.corrected'),
    action: correction.review_required ? t('income_corrections.review') : t('income_corrections.details'),
    correction,
  };
}

export function configureIncomeCorrections(context) {
  personId = context.personId;
  personName = context.personName || '';
  snapshot = context.snapshot;
  corrections = new Map((context.corrections || []).map((item) => [item.concept, item]));
}

export async function openIncomeCorrection(concept) {
  activeValue = snapshot?.values.find((value) => value.concept === concept) || null;
  if (!activeValue) return;
  activeCorrection = corrections.get(concept) || null;
  streamRevision = activeCorrection?.revision_number || 0;
  const sourceAtCorrection = activeCorrection?.source_at_correction || valueSource(activeValue);
  const currentUnderlying = activeCorrection?.current_underlying || valueSource(activeValue);

  elements.title.innerHTML = conceptMessage(
    activeCorrection ? 'income_corrections.correction_title' : 'income_corrections.correct_title',
    activeValue,
  );
  elements.context.textContent = `${personName} · ${t('income_corrections.tax_year', {year: snapshot.tax_year})}`;
  elements.status.hidden = !activeCorrection?.review_required;
  elements.status.textContent = activeCorrection?.review_required
    ? t('income_corrections.review_required')
    : '';
  elements.status.classList.toggle('review-required', Boolean(activeCorrection?.review_required));
  showSource(elements.sourceAmount, elements.sourceNote, sourceAtCorrection);
  showSource(elements.currentAmount, elements.currentNote, currentUnderlying);
  elements.form.elements.correct_amount.value = activeCorrection?.correct_amount || activeValue.amount;
  elements.form.elements.reason.value = activeCorrection?.reason || '';
  elements.remove.hidden = !activeCorrection;
  elements.confirm.hidden = !activeCorrection?.review_required;
  showDialogMessage('');
  elements.history.innerHTML = `<p class="field-note">${t('income_corrections.loading_history')}</p>`;
  elements.dialog.hidden = false;
  baseline = signature();
  updateSaveButton();
  try {
    await loadHistory();
  } catch (error) {
    showDialogMessage(error.message, true, error.language || 'en-CA');
  }
}

async function mutation(url, method, payload, successMessage) {
  setBusy(true);
  try {
    await requestJson(url, {
      method,
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    closeDialog();
    await reload();
    notify(successMessage, false, locale, true);
  } catch (error) {
    showDialogMessage(error.message, true, error.language || 'en-CA');
  } finally {
    setBusy(false);
  }
}

export function initializeIncomeCorrections(options) {
  elements = {
    dialog: document.querySelector('#income-correction-backdrop'),
    close: document.querySelector('#income-correction-close'),
    title: document.querySelector('#income-correction-title'),
    context: document.querySelector('#income-correction-context'),
    status: document.querySelector('#income-correction-status'),
    sourceAmount: document.querySelector('#income-correction-source-amount'),
    sourceNote: document.querySelector('#income-correction-source-note'),
    currentAmount: document.querySelector('#income-correction-current-amount'),
    currentNote: document.querySelector('#income-correction-current-note'),
    form: document.querySelector('#income-correction-form'),
    save: document.querySelector('#income-correction-save'),
    remove: document.querySelector('#income-correction-remove'),
    confirm: document.querySelector('#income-correction-confirm'),
    message: document.querySelector('#income-correction-message'),
    historyPanel: document.querySelector('#income-correction-history-panel'),
    history: document.querySelector('#income-correction-history'),
  };
  requestJson = options.requestJson;
  reload = options.reload;
  notify = options.notify;
  formatMoney = options.money;

  elements.close.addEventListener('click', closeDialog);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !elements.dialog.hidden) closeDialog();
  });
  elements.form.addEventListener('input', updateSaveButton);
  elements.form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(elements.form));
    if (activeCorrection) {
      await mutation(
        `/api/income/corrections/${activeCorrection.id}`,
        'PUT',
        {...values, expected_revision: activeCorrection.revision_number},
        conceptMessage('income_corrections.saved', activeValue),
      );
      return;
    }
    await mutation(
      '/api/income/corrections',
      'POST',
      {
        person_id: personId,
        tax_year: snapshot.tax_year,
        concept: activeValue.concept,
        ...values,
        expected_revision: streamRevision,
      },
      conceptMessage('income_corrections.saved', activeValue),
    );
  });
  elements.confirm.addEventListener('click', async () => {
    if (!activeCorrection) return;
    await mutation(
      `/api/income/corrections/${activeCorrection.id}/confirm`,
      'POST',
      {expected_revision: activeCorrection.revision_number},
      conceptMessage('income_corrections.confirmed', activeValue),
    );
  });
  elements.remove.addEventListener('click', async () => {
    if (!activeCorrection) return;
    await mutation(
      `/api/income/corrections/${activeCorrection.id}`,
      'DELETE',
      {expected_revision: activeCorrection.revision_number},
      conceptMessage('income_corrections.removed', activeValue),
    );
  });
}
