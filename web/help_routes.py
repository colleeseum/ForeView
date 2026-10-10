# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Searchable application and module help."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify

from expense_sources import expense_source_registry
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
        "key": "connections",
        "title": "Institution connections",
        "summary": "Manage supported live connections separately from document imports.",
        "body": (
            "The Connections page manages authorizations and synchronization for institutions "
            "that offer a live connection. Follow the institution's guide to connect an account. "
            "Use document imports from the financial record pages for statements and bills; "
            "they do not require a live connection."
        ),
        "keywords": ("connection", "authorization", "sync", "institution"),
        "category": "connections",
        "owning_page": "/connections",
    },
    {
        "key": "summary",
        "title": "Financial summary",
        "summary": "Review the latest available household financial facts.",
        "body": (
            "The Summary page brings together account balances, investments, real estate, "
            "liquidity, upcoming maturities, and recent transactions. Follow the financial "
            "record pages to review or update their underlying evidence. Missing or outdated "
            "records can affect the totals; the summary is not a financial projection."
        ),
        "keywords": ("summary", "dashboard", "household", "totals"),
        "category": "summary",
        "owning_page": "/",
    },
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
        "key": "expenses",
        "title": "Expenses",
        "summary": "Record and review factual household spending.",
        "body": (
            "Create required or discretionary categories, then add expenses manually or load "
            "statements from a supported source. Recorded totals use retained factual evidence "
            "and remain separate from projection assumptions. Resolve possible overlaps before "
            "relying on an annual total. For an incomplete year, a separately labelled seasonal "
            "estimate may be available when the preceding year provides a complete comparison. "
            "Use the related help topics for the estimation method and source-specific import "
            "instructions."
        ),
        "keywords": (
            "expense",
            "spending",
            "category",
            "required",
            "discretionary",
            "statement",
            "overlap",
            "estimate",
        ),
    },
    {
        "key": "expense-seasonal-estimate",
        "title": "Seasonal expense estimates",
        "summary": "Estimate an incomplete year without assuming utilities are linear.",
        "body": (
            "The estimate retains current-year actual statements and fills only uncovered dates "
            "from the same expense stream in the preceding year. Let A(y,C) be the current-year "
            "actual amount over covered dates C, P(U) the preceding-year amount for dates U "
            "that remain uncovered in the current year, and i the displayed inflation "
            "assumption. The estimate is E(y) = A(y,C) + (1 + i) × P(U). The current "
            "application assumption is i = 2.00%. Statement amounts are distributed over their "
            "actual service dates solely to align billing periods. Annual and one-time expenses "
            "are never extrapolated. An estimate is unavailable when the preceding year does "
            "not cover the full calendar year or prior overlaps remain unresolved. The estimate "
            "is planning information and never replaces the "
            "recorded factual total. This method preserves a prior seasonal pattern but cannot "
            "predict unusual weather, usage, tariff, or household changes."
        ),
        "keywords": (
            "expense",
            "seasonal",
            "estimate",
            "annual",
            "utility",
            "inflation",
            "Hydro",
            "Energir",
            "formula",
        ),
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


# Stable category IDs are shared by core and plugin-contributed articles.
_CATEGORIES = (
    ("financial", None, "Financial records"),
    ("summary", "financial", "Summary"),
    ("assets", "financial", "Assets"),
    ("accounts", "assets", "Accounts"),
    ("ownership", "assets", "Ownership"),
    ("real-estate", "assets", "Real estate"),
    ("income", "financial", "Income"),
    ("annual-records", "income", "Annual records"),
    ("tax-documents", "income", "Tax documents"),
    ("factual-corrections", "income", "Factual corrections"),
    ("expenses", "financial", "Expenses"),
    ("expense-categories", "expenses", "Categories"),
    ("expense-imports", "expenses", "Statement imports"),
    ("overlap", "expenses", "Overlap resolution"),
    ("seasonal", "expenses", "Seasonal estimates"),
    ("transactions", "financial", "Transactions"),
    ("imports", "transactions", "Imports"),
    ("reconciliation", "transactions", "Reconciliation"),
    ("planning", None, "Planning"),
    ("salary-projection", "planning", "Salary projection"),
    ("scenarios", "planning", "Scenarios"),
    ("public-rules", "planning", "Public tax rules"),
    ("application", None, "Application"),
    ("connections", "application", "Connections"),
    ("data-backups", "application", "Data and backups"),
    ("license", "application", "License"),
    ("disclaimer", "application", "Disclaimer"),
)
_CATEGORY_BY_ARTICLE = {
    "income": "annual-records",
    "factual-corrections": "factual-corrections",
    "assets": "assets",
    "transactions": "transactions",
    "expenses": "expenses",
    "expense-seasonal-estimate": "seasonal",
    "transaction-import": "imports",
    "transaction-reconcile": "reconciliation",
    "public-rule-approval": "public-rules",
}


def _categorize(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize every source through one shared category contract."""
    known = {key for key, _, _ in _CATEGORIES}
    categorized = []
    for index, article in enumerate(articles):
        item = dict(article)
        category = item.get("category") or _CATEGORY_BY_ARTICLE.get(item["key"], "application")
        if category not in known:
            category = "application"
        item["category"] = category
        item["parent_topic"] = item.get("parent_topic")
        item["order"] = item.get("order", index)
        item["owning_page"] = item.get("owning_page")
        categorized.append(item)
    return categorized


@blueprint.get("/api/help")
def help_catalog():
    articles: list[dict[str, Any]] = list(_ARTICLES)
    articles.extend(
        {
            "key": f"income-source-{source.key}",
            "title": f"Loading a T1 from {source.display_name}",
            "summary": f"How to obtain and load a {source.display_name} document.",
            "body": source.help_text,
            "keywords": ("T1", "PDF", "tax return", source.key, source.display_name),
            "category": "tax-documents",
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
            "category": "tax-documents",
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
            "category": "annual-records",
        }
        for source in public_pension_source_registry.providers
    )
    articles.extend(
        {
            "key": f"expense-source-{source.key}",
            "title": f"Loading {source.display_name}",
            "summary": "Import household expense statement from a supported source.",
            "body": source.help_text,
            "keywords": ("expense", "statement", "PDF", source.key, source.display_name),
            "category": "expense-imports",
        }
        for source in expense_source_registry.providers
    )
    articles.extend(
        {
            "key": f"institution-{provider.key}-{topic.key}",
            "title": topic.title,
            "summary": f"Help supplied by the {provider.display_name} module.",
            "body": topic.body,
            "keywords": (provider.key, provider.display_name, topic.key, "institution"),
            "category": topic.category,
            "parent_topic": topic.parent_topic,
            "order": topic.order,
            "owning_page": topic.owning_page,
        }
        for provider in institution_registry().providers
        for topic in provider.help_topics
    )
    return jsonify(
        {
            "language": "en-CA",
            "tooltips": list(_TOOLTIPS),
            "categories": [
                {"key": key, "parent": parent, "title": title, "order": index}
                for index, (key, parent, title) in enumerate(_CATEGORIES)
            ],
            "articles": _categorize(articles),
        }
    )
