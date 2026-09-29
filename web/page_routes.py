from datetime import date

from flask import Blueprint, render_template

from institution_support import institution_registry

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
    return render_template("income.html", latest_tax_year=date.today().year - 1)


@blueprint.get("/connections")
def connections_page():
    return render_template("connections.html")


@blueprint.get("/transactions")
def transactions_page():
    return render_template("transactions.html", import_help=institution_registry().import_help())
