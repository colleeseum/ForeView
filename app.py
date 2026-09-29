from __future__ import annotations

import argparse
import hmac
import os
import secrets
import urllib as urllib
from pathlib import Path

from flask import Flask, abort, request, session

from infrastructure.runtime_config import RuntimeConfig
from institution_support.connection_provider import ConnectionProvider
from institution_support.registry import institution_registry
from services.database_initialization import ensure_domain_schema as ensure_domain_schema
from services.database_initialization import initialize_database
from web.dashboard_routes import blueprint as dashboard_blueprint
from web.income_routes import blueprint as income_blueprint
from web.institution_routes import blueprint as institution_blueprint
from web.model_routes import blueprint as model_blueprint
from web.page_routes import blueprint as page_blueprint
from web.public_rule_routes import blueprint as public_rule_blueprint
from web.salary_projection_routes import blueprint as salary_projection_blueprint

ROOT = Path(__file__).parent
PROFILE_DATA_DIRS = {
    "dev": ROOT / ".runtime" / "dev",
    "prod": Path.home() / ".local" / "share" / "retirement-finance" / "prod",
}


def profile_data_dir(profile: str) -> Path:
    try:
        return PROFILE_DATA_DIRS[profile]
    except KeyError as error:
        raise ValueError(f"Unknown runtime profile: {profile}") from error


def default_data_dir() -> Path:
    """The runtime folder chosen by FINANCE_DATA_DIR, else FINANCE_PROFILE (default dev)."""
    configured = os.environ.get("FINANCE_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return profile_data_dir(os.environ.get("FINANCE_PROFILE", "dev"))


def initialize(runtime: RuntimeConfig) -> None:
    """Apply schema and data repairs for a runtime before serving it."""
    initialize_database(runtime.connect)


def connection_providers(runtime: RuntimeConfig) -> dict[str, ConnectionProvider]:
    """Runtime adapters for every institution that declares a live connection."""
    context = runtime.context()
    adapters = (
        provider.connection.create_provider(context)
        for provider in institution_registry().providers
        if provider.connection and provider.connection.create_provider
    )
    return {adapter.institution_key: adapter for adapter in adapters}


def create_app(runtime: RuntimeConfig) -> Flask:
    """Build the web application for one runtime.

    Routes reach the runtime through ``app.extensions["finance_runtime"]``, read
    on each request, so nothing about the runtime is stored at module level.
    """
    app = Flask(__name__)
    app.secret_key = runtime.setting("RETIREMENT_APP_SECRET") or secrets.token_hex(32)
    app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
    app.extensions["finance_runtime"] = runtime

    def csrf_token() -> str:
        token = session.get("csrf_token")
        if not isinstance(token, str):
            token = secrets.token_urlsafe(32)
            session["csrf_token"] = token
        return token

    @app.before_request
    def verify_csrf_token() -> None:
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return
        expected = session.get("csrf_token")
        supplied = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
        if (
            not isinstance(expected, str)
            or not supplied
            or not hmac.compare_digest(expected, supplied)
        ):
            abort(403, description="Missing or invalid CSRF token.")

    app.jinja_env.globals["csrf_token"] = csrf_token

    def current_runtime() -> RuntimeConfig:
        return app.extensions["finance_runtime"]

    app.extensions["finance_connect"] = lambda: current_runtime().connect()
    app.extensions["finance_connection_providers"] = lambda: connection_providers(current_runtime())
    app.extensions["finance_public_rules_path"] = lambda: ROOT / "public_rules"
    for blueprint in (
        page_blueprint,
        dashboard_blueprint,
        institution_blueprint,
        income_blueprint,
        model_blueprint,
        public_rule_blueprint,
        salary_projection_blueprint,
    ):
        app.register_blueprint(blueprint)
    for institution in institution_registry().providers:
        if institution.connection and institution.connection.routes:
            app.register_blueprint(institution.connection.routes)
    for rule, endpoint in (
        ("/", "index"),
        ("/setup", "setup"),
        ("/accounts", "accounts_page"),
        ("/income", "income_page"),
        ("/connections", "connections_page"),
        ("/transactions", "transactions_page"),
        ("/settings", "settings_page"),
    ):
        app.add_url_rule(rule, endpoint=endpoint, build_only=True)
    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the local retirement application")
    runtime_group = parser.add_mutually_exclusive_group()
    runtime_group.add_argument(
        "--profile", choices=sorted(PROFILE_DATA_DIRS), help="Use a named runtime profile"
    )
    runtime_group.add_argument(
        "--data-dir", type=Path, help="Directory containing finance.sqlite3 and finance.config.json"
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable Flask debug mode and automatic reload"
    )
    parser.add_argument(
        "--port", type=int, help="Listening port; defaults to 5124 for dev and 5123 otherwise"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Listening address; defaults to localhost. Use 0.0.0.0 only on a trusted network.",
    )
    arguments = parser.parse_args()
    if arguments.data_dir:
        data_dir = arguments.data_dir
    elif arguments.profile:
        data_dir = profile_data_dir(arguments.profile)
    else:
        data_dir = default_data_dir()
    runtime = RuntimeConfig.load(data_dir)
    initialize(runtime)
    print(f"Runtime data: {runtime.data_dir}")
    selected_profile = arguments.profile or os.environ.get("FINANCE_PROFILE", "dev")
    debug_mode = arguments.debug or (arguments.data_dir is None and selected_profile == "dev")
    port = arguments.port or (
        5124 if selected_profile == "dev" and arguments.data_dir is None else 5123
    )
    create_app(runtime).run(
        host=arguments.host, port=port, debug=debug_mode, ssl_context=runtime.ssl_context()
    )
