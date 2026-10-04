# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3

from flask import jsonify, request

from repositories.person_repository import PersonRepository
from web.dependencies import dependency
from web.model_blueprint import blueprint


@blueprint.get("/api/model/people")
def model_people():
    with dependency("connect")() as connection:
        people = PersonRepository(connection).list_all()
        return jsonify(
            {
                "people": [
                    {"id": person.id, "name": person.name, "birth_date": person.birth_date}
                    for person in people
                ]
            }
        )


@blueprint.post("/api/model/people")
def add_person_route():
    payload = request.get_json(silent=True) or {}
    try:
        with dependency("connect")() as connection:
            person = PersonRepository(connection).create(
                str(payload["name"]), payload.get("birth_date")
            )
        return jsonify({"id": person.id}), 201
    except (KeyError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify({"error": str(error)}), 400


@blueprint.put("/api/model/people/<int:person_id>")
def update_person_route(person_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        with dependency("connect")() as connection:
            PersonRepository(connection).update_birth_date(person_id, str(payload["birth_date"]))
        return jsonify({"updated": True})
    except (KeyError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify({"error": str(error)}), 400
