# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import hmac
import secrets
import urllib.parse

from flask import Blueprint, jsonify, redirect, request, session

from web.dependencies import dependency

blueprint = Blueprint("questrade", __name__)


@blueprint.get("/api/questrade/status")
@blueprint.get("/api/connections/questrade/status")
def questrade_status():
    provider = dependency("connection_providers")()["questrade"]
    return jsonify(provider.status())


@blueprint.post("/api/questrade/sync")
@blueprint.post("/api/connections/questrade/sync")
def questrade_sync():
    provider = dependency("connection_providers")()["questrade"]
    payload = request.get_json(silent=True) or {}
    requested = payload.get("connection")
    # Re-fetch activity from this date instead of from the previous sync.
    fetch_from = payload.get("fetch_from") or None
    names = [requested] if requested else provider.configured_connections()
    results = []
    errors: list[dict[str, object]] = []
    for name in names:
        try:
            result = (
                provider.synchronize(str(name), fetch_from=fetch_from)
                if fetch_from
                else provider.synchronize(str(name))
            )
            results.append(result)
            errors.extend(
                {"connection": name, **component_error}
                for component_error in result.get("errors", [])
            )
        except RuntimeError as exc:
            errors.append({"connection": name, "error": str(exc)})
    status = 200 if results and not errors else (207 if results else 502)
    return jsonify({"results": results, "errors": errors}), status


@blueprint.post("/api/questrade/refresh")
@blueprint.post("/api/connections/questrade/refresh")
def questrade_refresh():
    connection_name = request.args.get("connection", "default").strip()
    provider = dependency("connection_providers")()["questrade"]
    try:
        provider.refresh(connection_name)
    except RuntimeError as exc:
        return redirect(f"/connections?questrade=error&message={urllib.parse.quote(str(exc))}")
    return redirect("/connections?questrade=refreshed")


@blueprint.get("/api/questrade/connect")
@blueprint.get("/api/connections/questrade/connect")
def questrade_connect():
    provider = dependency("connection_providers")()["questrade"]
    connection_name = request.args.get("connection", "default").strip()
    if not connection_name or len(connection_name) > 80:
        return jsonify({"error": "A connection name is required."}), 400
    state = secrets.token_urlsafe(32)
    session["questrade_oauth_state"] = {"value": state, "connection": connection_name}
    try:
        return redirect(provider.authorization_url(connection_name, state))
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503


@blueprint.get("/questrade/callback")
@blueprint.get("/connections/questrade/callback")
def questrade_callback():
    error = request.args.get("error")
    if error:
        return redirect(f"/connections?questrade=error&message={urllib.parse.quote(error)}")
    oauth_state = session.pop("questrade_oauth_state", None) or {}
    expected_state = oauth_state.get("value")
    connection_name = oauth_state.get("connection", "default")
    if not expected_state or not hmac.compare_digest(expected_state, request.args.get("state", "")):
        return "Invalid Questrade OAuth state.", 400
    code = request.args.get("code")
    provider = dependency("connection_providers")()["questrade"]
    if not code or not provider.profile(connection_name):
        return "Missing Questrade authorization code or client configuration.", 400
    try:
        provider.complete_authorization(connection_name, code)
        return redirect("/connections?questrade=connected")
    except RuntimeError as exc:
        return redirect(f"/accounts?questrade=error&message={urllib.parse.quote(str(exc))}")
