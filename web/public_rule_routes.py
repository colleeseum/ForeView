# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Review and approve version-controlled public financial rules."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for

from projection.tax import EffectiveMarginalRateService
from repositories.public_rule_approval_repository import PublicRuleApprovalRepository
from services.public_rule_catalog import PublicRuleCatalog

blueprint = Blueprint("public_rules", __name__)

_JURISDICTION_LABELS = {
    "CA": "Federal",
    "CA-AB": "Alberta",
    "CA-BC": "British Columbia",
    "CA-MB": "Manitoba",
    "CA-NB": "New Brunswick",
    "CA-NL": "Newfoundland and Labrador",
    "CA-NT": "Northwest Territories",
    "CA-NS": "Nova Scotia",
    "CA-NU": "Nunavut",
    "CA-ON": "Ontario",
    "CA-PE": "Prince Edward Island",
    "CA-QC": "Quebec",
    "CA-SK": "Saskatchewan",
    "CA-YT": "Yukon",
}


def _catalog() -> PublicRuleCatalog:
    return PublicRuleCatalog(current_app.extensions["finance_public_rules_path"]())


@blueprint.get("/settings")
def settings():
    packages = _catalog().list_packages()
    jurisdiction_codes = sorted(
        {package.rule_set.jurisdiction for package in packages},
        key=lambda code: (
            (list(_JURISDICTION_LABELS).index(code), code)
            if code in _JURISDICTION_LABELS
            else (len(_JURISDICTION_LABELS), code)
        ),
    )
    jurisdictions = [
        {"code": code, "label": _JURISDICTION_LABELS.get(code, code)} for code in jurisdiction_codes
    ]
    requested_jurisdiction = request.args.get("jurisdiction")
    selected_jurisdiction = (
        requested_jurisdiction
        if requested_jurisdiction in jurisdiction_codes
        else (jurisdiction_codes[0] if jurisdiction_codes else None)
    )
    jurisdiction_packages = [
        package for package in packages if package.rule_set.jurisdiction == selected_jurisdiction
    ]
    years = sorted({package.rule_set.tax_year for package in jurisdiction_packages}, reverse=True)
    requested_year = request.args.get("year", type=int)
    selected_year = requested_year if requested_year in years else (years[0] if years else None)
    selected_packages = [
        package for package in jurisdiction_packages if package.rule_set.tax_year == selected_year
    ]
    combined_rates = _combined_rates(packages, selected_packages, selected_year)
    with current_app.extensions["finance_connect"]() as connection:
        repository = PublicRuleApprovalRepository(connection)
        rows = [
            {
                "package": package,
                "approval": repository.get(package.rule_set.rule_set_id, package.content_hash),
            }
            for package in selected_packages
        ]
    return render_template(
        "public_rules.html",
        rows=rows,
        jurisdictions=jurisdictions,
        selected_jurisdiction=selected_jurisdiction,
        years=years,
        selected_year=selected_year,
        combined_rates=combined_rates,
    )


def _combined_rates(packages, selected_packages, selected_year):
    if not selected_packages or selected_year is None:
        return None
    federal = next(
        (
            package.rule_set
            for package in packages
            if package.rule_set.jurisdiction == "CA" and package.rule_set.tax_year == selected_year
        ),
        None,
    )
    if federal is None:
        return None
    schedule = EffectiveMarginalRateService().calculate(federal, selected_packages[0].rule_set)
    if schedule is None:
        return None
    return tuple(
        {
            "upper_bound": None if item.upper_bound is None else f"${item.upper_bound:,.0f}",
            "rate": (
                f"{(item.rate * Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}%"
            ),
        }
        for item in schedule
    )


@blueprint.post("/public-rules/<rule_set_id>/approve")
def approve_public_rule(rule_set_id: str):
    package = _catalog().get(rule_set_id)
    if package is None:
        abort(404)
    submitted_hash = request.form.get("content_hash", "")
    if submitted_hash != package.content_hash:
        abort(409, "The rule package changed. Review its current values before approving it.")
    with current_app.extensions["finance_connect"]() as connection:
        PublicRuleApprovalRepository(connection).approve(rule_set_id, package.content_hash)
    return redirect(
        url_for(
            "public_rules.settings",
            jurisdiction=package.rule_set.jurisdiction,
            year=package.rule_set.tax_year,
        )
    )
