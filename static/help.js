const helpContent = {
  assets: {
    title: 'Assets',
    body: 'Accounts are separated by their retirement and tax rules. Non-registered, TFSA, and RRSP balances are shown independently. Property will be added as a separate asset type later.'
  },
  transactions: {
    title: 'Transactions',
    body: 'Use the tabs to keep Non-registered, TFSA, and RRSP activity separate. The account filter narrows the active category to one account.'
  },
  'transaction-import': {
    title: 'Transaction import',
    body: 'Use the institution native export when possible. Supported institution formats are listed in the import dialog. Overlapping imports are deduplicated, and recognized statements may update balances, holdings, rates, or maturities.'
  },
  'transaction-reconcile': {
    title: 'Reconcile statement',
    body: 'Enter a balance you know to be correct for the selected account, or import a supported statement PDF, which is compared with the imported activity for its period. When the ledger matches, the account is reconciled through that date. Later imports that would add transactions to a reconciled period ask for confirmation first; if you continue, the period is checked again and marked as needing review when it no longer matches, until you reconcile it again.'
  },
  'public-rule-approval': {
    title: 'Approving public rules',
    body: 'Approval records that you reviewed this exact version of the public-rule data. It does not certify that the extraction is complete or correct. You are responsible for comparing it with the linked official sources, verifying the values, and checking whether the jurisdiction added, removed, or changed any tax concept, calculation rule, credit, contribution, threshold, phase-out, surtax, or indexation mechanism. The importer may require a code change when the rules change structurally. Approve the data only after confirming it is accurate and complete for financial projections.'
  }
};

const helpPopover = document.createElement('section');
helpPopover.className = 'help-popover';
helpPopover.hidden = true;
helpPopover.setAttribute('role', 'dialog');
helpPopover.innerHTML = '<button class="help-popover-close" type="button" aria-label="Close help">×</button><h2></h2><p></p>';
document.body.append(helpPopover);

function closeHelp() { helpPopover.hidden = true; }
function openHelp(key, anchor) {
  const content = helpContent[key];
  if (!content) return;
  helpPopover.querySelector('h2').textContent = content.title;
  helpPopover.querySelector('p').textContent = content.body;
  helpPopover.hidden = false;
  const box = anchor.getBoundingClientRect();
  helpPopover.style.top = `${Math.min(box.bottom + 8, window.innerHeight - 220)}px`;
  helpPopover.style.left = `${Math.min(Math.max(16, box.left), window.innerWidth - 360)}px`;
}
window.openContextHelp = (key) => {
  const button = document.querySelector(`[data-help-key="${key}"]`);
  if (button) openHelp(key, button);
};

document.querySelectorAll('[data-help-key]').forEach((button) => button.addEventListener('click', (event) => {
  event.stopPropagation();
  openHelp(button.dataset.helpKey, button);
}));
helpPopover.querySelector('.help-popover-close').addEventListener('click', closeHelp);
document.addEventListener('click', (event) => {
  if (!helpPopover.hidden && !helpPopover.contains(event.target) && !event.target.closest('[data-help-key]')) closeHelp();
});
document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeHelp(); });
