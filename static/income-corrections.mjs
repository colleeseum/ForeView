import {formSignature} from './form-state.mjs';
import {escapeHtml} from './html.mjs';

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

function sourceDetails(source) {
  return [
    source?.source,
    source?.document_kind,
    source?.jurisdiction,
    source?.line_code ? `line ${source.line_code}` : null,
    source?.source_version ? `version ${source.source_version}` : null,
    source?.document_hash ? `document ${source.document_hash}` : null,
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
  amountElement.textContent = source?.amount == null ? 'No current value' : formatMoney(source.amount);
  noteElement.textContent = sourceDetails(source) || 'No source provenance is available.';
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

function showDialogMessage(message, error = false) {
  elements.message.textContent = message;
  elements.message.classList.toggle('error', error);
}

function revisionLabel(kind) {
  return {
    create: 'Created', edit: 'Edited', confirm: 'Source review confirmed', remove: 'Removed',
  }[kind] || kind;
}

function renderHistory(revisions) {
  if (!revisions.length) {
    elements.history.innerHTML = '<p class="field-note">No correction revisions exist.</p>';
    elements.historyPanel.open = false;
    return;
  }
  elements.history.innerHTML = revisions.slice().reverse().map((revision) => `
    <article class="income-correction-revision">
      <div><strong>Revision ${revision.revision_number}</strong><span>${escapeHtml(revisionLabel(revision.revision_kind))}</span><time>${escapeHtml(revision.created_at)}</time></div>
      <p>${revision.correct_amount == null ? 'No effective correction' : formatMoney(revision.correct_amount)} · ${escapeHtml(revision.reason)}</p>
      <small>Source reviewed: ${revision.source_at_correction.amount == null ? 'none' : formatMoney(revision.source_at_correction.amount)} · ${escapeHtml(sourceDetails(revision.source_at_correction) || 'no provenance')}</small>
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
    badge: correction.review_required ? 'Review required' : 'Corrected',
    action: correction.review_required ? 'Review' : 'Details',
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

  elements.title.textContent = activeCorrection
    ? `${activeValue.label} correction`
    : `Correct ${activeValue.label.toLocaleLowerCase()}`;
  elements.context.textContent = `${personName} · Tax year ${snapshot.tax_year}`;
  elements.status.hidden = !activeCorrection?.review_required;
  elements.status.textContent = activeCorrection?.review_required
    ? 'Review required: the current underlying value or provenance has changed.'
    : '';
  elements.status.classList.toggle('review-required', Boolean(activeCorrection?.review_required));
  showSource(elements.sourceAmount, elements.sourceNote, sourceAtCorrection);
  showSource(elements.currentAmount, elements.currentNote, currentUnderlying);
  elements.form.elements.correct_amount.value = activeCorrection?.correct_amount || activeValue.amount;
  elements.form.elements.reason.value = activeCorrection?.reason || '';
  elements.remove.hidden = !activeCorrection;
  elements.confirm.hidden = !activeCorrection?.review_required;
  showDialogMessage('');
  elements.history.innerHTML = '<p class="field-note">Loading revision history…</p>';
  elements.dialog.hidden = false;
  baseline = signature();
  updateSaveButton();
  try {
    await loadHistory();
  } catch (error) {
    showDialogMessage(error.message, true);
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
    notify(successMessage);
  } catch (error) {
    showDialogMessage(error.message, true);
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
        `${activeValue.label} correction saved.`,
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
      `${activeValue.label} correction saved.`,
    );
  });
  elements.confirm.addEventListener('click', async () => {
    if (!activeCorrection) return;
    await mutation(
      `/api/income/corrections/${activeCorrection.id}/confirm`,
      'POST',
      {expected_revision: activeCorrection.revision_number},
      `${activeValue.label} correction confirmed against the current source.`,
    );
  });
  elements.remove.addEventListener('click', async () => {
    if (!activeCorrection) return;
    await mutation(
      `/api/income/corrections/${activeCorrection.id}`,
      'DELETE',
      {expected_revision: activeCorrection.revision_number},
      `${activeValue.label} correction removed. Source precedence restored.`,
    );
  });
}
