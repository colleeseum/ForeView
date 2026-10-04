from datetime import date

from flask import Blueprint, render_template

from income_sources import income_source_registry
from institution_support import institution_registry
from public_pension_sources import public_pension_source_registry
from tax_notices import tax_notice_registry

blueprint = Blueprint("pages", __name__)


@blueprint.get("/")
def index():
    return render_template("index.html")


@blueprint.get("/setup")
def setup():
    return render_template("setup.html")


@blueprint.get("/application-settings")
def application_settings():
    return render_template("application_settings.html")


@blueprint.get("/accounts")
def accounts_page():
    return render_template("accounts.html")


@blueprint.get("/income")
def income_page():
    return render_template(
        "income.html",
        latest_tax_year=date.today().year - 1,
        income_sources=income_source_registry.providers,
        tax_notice_sources=tax_notice_registry.providers,
        public_pension_sources=public_pension_source_registry.providers,
    )


@blueprint.get("/about")
def about_page():
    return render_template(
        "about.html",
        income_sources=income_source_registry.providers,
        tax_notice_sources=tax_notice_registry.providers,
        public_pension_sources=public_pension_source_registry.providers,
        institutions=institution_registry().providers,
    )


@blueprint.get("/connections")
def connections_page():
    return render_template("connections.html")


@blueprint.get("/transactions")
def transactions_page():
    return render_template("transactions.html", import_help=institution_registry().import_help())
