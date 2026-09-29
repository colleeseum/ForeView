# Tax document concepts

The financial record retains tax-document facts even when no projection algorithm consumes them yet.
Values are normalized by tax year, effective year, document kind, jurisdiction, concept, and line code.
Assessment values preserve both the amount reported by the taxpayer and the amount determined by the authority.

## Filed T1 returns

The UFile importer recognizes these useful concept groups when they appear on the individual return summary:

- employment and self-employment income;
- OAS, CPP/QPP, other pension, split-pension, RRSP, FHSA, and RDSP income;
- dividends, interest and other investment income, rental income, partnership income, and taxable capital gains;
- support payments, scholarships, workers' compensation, social assistance, and federal supplements;
- registered-plan, employment, moving, child-care, support, carrying-charge, payroll-contribution, and other deductions;
- total income, net income, taxable income, tax payable, tax withheld, credits, refund, and balance owing;
- CPP/QPP, EI, and QPIP contribution facts used to validate payroll projections.

Line 12100 interest is also exposed directly in the annual-record editor and history table. Account-derived interest must eventually reconcile to this filed total rather than be added to it.

## CRA notices of assessment

The model retains:

- assessed income, deductions, taxable income, tax, withholding, credits, Quebec abatement, and assessment balance;
- the amount of withholding transferred to Quebec;
- the next-year Canada training credit limit;
- the complete RRSP room calculation, including prior limit, deducted contributions, unused room, earned room, pension adjustment, prescribed amount, past-service adjustment, pension-adjustment reversal, unused contributions, deduction limit, and available contribution room.

The typed assessment and registered-plan-room records remain the stable projection-facing summaries. The normalized values retain the supporting detail.

## Revenu Québec notices of assessment

The model retains reported and determined values for useful income, deduction, credit, contribution, withholding, tax, and balance lines. It also retains interest charged on an assessed balance. This supports later comparison of the filed return with the authority's determination.

## Deliberately excluded

Social insurance numbers, tax-account identifiers, addresses, notice numbers, banking instructions, payment codes, contact instructions, and generic dispute or privacy text are not stored. They do not improve projection accuracy and would increase the amount of sensitive data retained.
