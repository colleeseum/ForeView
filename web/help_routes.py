# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Searchable application and module help."""

from __future__ import annotations

from flask import Blueprint, jsonify

from income_sources import income_source_registry
from institution_support import institution_registry
from public_pension_sources import public_pension_source_registry
from tax_notices import tax_notice_registry

blueprint = Blueprint("help", __name__)

_TOOLTIPS = (
    {
        "key": "employment-income",
        "title": "Employment income",
        "body": "Employment income reported on T1 line 10100 before subtracting a recorded bonus.",
    },
    {
        "key": "salary-rate",
        "title": "Salary rate",
        "body": "Employment income minus the bonus included in that income.",
    },
    {
        "key": "rrsp-contribution",
        "title": "RRSP contribution",
        "body": "Cash deposited into an RRSP during the year. This is not contribution room.",
    },
)

_ARTICLES = (
    {
        "key": "income",
        "title": "Employment income records",
        "summary": "Record factual annual employment and tax-return values.",
        "body": (
            "Employment income records retain factual values by person and tax year. "
            "You can enter a record manually or load a supported T1 PDF. A loaded PDF is "
            "analysed for preview only and is not stored. Review every value before saving."
        ),
        "keywords": ("income", "employment", "T1", "tax", "salary", "actual"),
    },
    {
        "key": "factual-corrections",
        "title": "Correcting a factual income or tax value",
        "summary": "Override an inaccurate retained fact without changing its source document.",
        "body": (
            "Use a factual correction when the application should use a different value from "
            "the assessment, filed return, or annual record it retained. Enter the corrected "
            "amount and explain why it differs. The original value and provenance remain "
            "available for audit, and the correction is clearly identified as a user override. "
            "If a new import changes the underlying value or source, the correction remains "
            "active but requires review. Confirm it only after comparing the current source. "
            "Remove the correction when ordinary source precedence should apply again. Reimport "
            "the document instead when the retained source itself is incomplete or outdated."
        ),
        "keywords": (
            "income",
            "tax",
            "correction",
            "override",
            "source",
            "review",
            "provenance",
        ),
    },
    {
        "key": "assets",
        "title": "Assets and accounts",
        "summary": "Understand account categories, balances, and ownership.",
        "body": (
            "Accounts are separated by the tax and retirement rules that apply to them. "
            "Non-registered, TFSA, RRSP, RESP, and real-estate values are tracked separately."
        ),
        "keywords": ("asset", "account", "balance", "ownership", "GIC"),
    },
    {
        "key": "transactions",
        "title": "Transactions",
        "summary": "Review imported cash-flow history by account category.",
        "body": (
            "Transaction tabs keep activity under the account category whose rules apply. "
            "Use the account filter to narrow the current category to one account."
        ),
        "keywords": ("transaction", "cash flow", "account", "history"),
    },
    {
        "key": "transaction-import",
        "title": "Importing bank documents",
        "summary": "Supported statements, exports, deduplication, and account confirmation.",
        "body": (
            "Use the institution's native PDF or CSV export when possible. The application "
            "detects registered institution modules, previews newly detected accounts for "
            "confirmation, and deduplicates overlapping imports. Recognized documents may "
            "update transactions, balances, holdings, rates, or maturities. Search for the "
            "institution name to find module-specific formats."
        ),
        "keywords": ("bank", "PDF", "CSV", "statement", "import", "institution"),
    },
    {
        "key": "transaction-reconcile",
        "title": "Reconciling a statement",
        "summary": "Compare ledger activity with a known account balance.",
        "body": (
            "Enter a known balance or import a supported statement. When the ledger matches, "
            "the account is reconciled through that date. A later import into the reconciled "
            "period triggers confirmation and may mark the checkpoint for review."
        ),
        "keywords": ("reconcile", "statement", "balance", "checkpoint", "ledger"),
    },
    {
        "key": "public-rule-approval",
        "title": "Approving public rules",
        "summary": "What approval confirms and what must still be reviewed.",
        "body": (
            "Approval records that you reviewed the exact content hash. It does not certify "
            "that extraction is complete or correct. Compare the values with official sources "
            "and check for added, removed, or changed tax concepts, calculations, credits, "
            "contributions, thresholds, phase-outs, surtaxes, and indexation mechanisms. "
            "Structural rule changes may require an importer code change."
        ),
        "keywords": ("tax", "rules", "approve", "hash", "government", "payroll"),
    },
)


@blueprint.get("/api/help")
def help_catalog():
    articles = list(_ARTICLES)
    articles.extend(
        {
            "key": f"income-source-{source.key}",
            "title": f"Loading a T1 from {source.display_name}",
            "summary": f"How to obtain and load a {source.display_name} document.",
            "body": source.help_text,
            "keywords": ("T1", "PDF", "tax return", source.key, source.display_name),
        }
        for source in income_source_registry.providers
    )
    articles.extend(
        {
            "key": f"tax-notice-{source.key}",
            "title": f"Loading {source.display_name}",
            "summary": "Import authoritative assessed tax values.",
            "body": source.help_text,
            "keywords": ("notice", "assessment", "tax", source.key, source.display_name),
        }
        for source in tax_notice_registry.providers
    )
    articles.extend(
        {
            "key": f"public-pension-{source.key}",
            "title": f"Loading {source.display_name}",
            "summary": "Import public-pension earnings and official estimates.",
            "body": source.help_text,
            "keywords": ("CPP", "QPP", "pension", "statement", source.key),
        }
        for source in public_pension_source_registry.providers
    )
    articles.extend(
        {
            "key": f"institution-{provider.key}-{topic.key}",
            "title": topic.title,
            "summary": f"Help supplied by the {provider.display_name} module.",
            "body": topic.body,
            "keywords": (provider.key, provider.display_name, topic.key, "institution"),
        }
        for provider in institution_registry().providers
        for topic in provider.help_topics
    )
    return jsonify({"tooltips": list(_TOOLTIPS), "articles": articles})
