export function importMessage(data) {
  const reconciliation = (data.results || []).find((item) => item.reconciliation_status);
  if (reconciliation) {
    if (reconciliation.reconciliation_status === 'reconciled') {
      return `Statement reconciled: ${reconciliation.csv_transaction_count} CSV transactions matched the PDF closing balance.`;
    }
    if (reconciliation.reconciliation_status === 'no_matching_transactions') {
      return 'Statement loaded, but no CSV transactions matched its statement period.';
    }
    return `Statement difference: $${Number(reconciliation.difference || 0).toFixed(2)}. Review the CSV period and missing transactions.`;
  }
  const tfsa = (data.results || []).filter((item) => item.document_type === 'statement' || item.document_type === 'maturity_notice');
  if (tfsa.length) {
    const interestRows = tfsa.reduce((sum, item) => sum + Number(item.imported || 0), 0);
    const gics = tfsa.reduce((sum, item) => sum + Number(item.gics || 0), 0);
    return `RBC TFSA PDF loaded: ${interestRows} interest entr${interestRows === 1 ? 'y' : 'ies'} and ${gics} CPG record${gics === 1 ? '' : 's'}.`;
  }
  return `${data.imported} transaction${data.imported === 1 ? '' : 's'} imported from ${data.files} file${data.files === 1 ? '' : 's'}.`;
}
