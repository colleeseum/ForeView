Download the electricity bill PDF from your Hydro-Québec account, then choose that PDF in the
expense import dialog. Review the detected amount, service period, expense name, category, and
association before saving.

Bills containing multiple contracts or service periods are not currently supported. Record each
contract manually until separate imported evidence is supported.

Hydro-Québec bills contain French and English labels. The module reads the current bill amount
labelled `Montant de la présente facture` or `Amount of this bill` and the service period under
`DÉTAIL DES COÛTS`. It does not use a prior balance, payment, or combined amount due. The first
printed date can be a meter-reading boundary, so the retained service period begins on the following
calendar day when the bill's printed day count requires that adjustment.

Equalized Payments Plan annual-review bills are rejected because their billed amount can include an
EPP balance or an adjustment from a prior period rather than only the current service-period cost.

Hydro-Québec can change its PDF layout. An unsupported or unreadable document is rejected rather
than imported with guessed values. The PDF itself is not retained; ForeView stores its filename,
content hash, parser version, and the confirmed expense evidence.
