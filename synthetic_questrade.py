"""Replay invented Questrade responses into a synthetic runtime."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from domain.questrade_authorization import QuestradeAuthorization
from infrastructure.runtime_config import RuntimeConfig
from institutions.questrade.sync import sync_questrade_connection
from repositories.account_ownership_repository import AccountOwnershipRepository
from repositories.account_repository import AccountRepository
from repositories.person_repository import PersonRepository
from repositories.questrade_authorization_repository import QuestradeAuthorizationRepository
from services.database_initialization import initialize_database

SCENARIOS = Path(__file__).parent / "tests/fixtures/questrade/sync_scenarios.json"


class SyntheticQuestradeAPI:
    """Serve one deterministic Questrade response scenario."""

    def __init__(self, scenario: dict[str, Any]):
        self.scenario = scenario
        self.activity_responses: set[tuple[str, str]] = set()

    def __call__(self, authorization: QuestradeAuthorization, path: str) -> dict[str, object]:
        connection = self.scenario[authorization.name]
        if path == "/v1/accounts":
            return {
                "accounts": [
                    {"number": item["number"], "type": item["type"]}
                    for item in connection["accounts"]
                ]
            }
        account_number = path.split("/v1/accounts/", 1)[1].split("/", 1)[0]
        account = next(item for item in connection["accounts"] if item["number"] == account_number)
        if path.endswith("/balances"):
            return {
                "combinedBalances": [
                    {"currency": "USD", "totalEquity": account["balance"] * 0.75},
                    {"currency": "CAD", "totalEquity": account["balance"]},
                ]
            }
        if path.endswith("/positions"):
            return {"positions": account["positions"]}
        if "/executions?" in path:
            return {"executions": account["executions"]}
        if "/activities?" in path:
            key = (authorization.name, account_number)
            if key in self.activity_responses:
                return {"activities": []}
            self.activity_responses.add(key)
            return {"activities": account["activities"]}
        raise AssertionError(f"Unexpected synthetic Questrade path: {path}")


def read_scenario(name: str) -> dict[str, Any]:
    scenarios = json.loads(SCENARIOS.read_text())
    try:
        return scenarios[name]
    except KeyError as error:
        raise ValueError(f"Unknown synthetic Questrade scenario: {name}") from error


def load_synthetic_questrade(data_dir: Path, scenario_name: str = "initial") -> list[dict]:
    """Replay a scenario into a runtime that is explicitly marked synthetic."""
    target = data_dir.expanduser().resolve()
    config_path = target / "finance.config.json"
    config = json.loads(config_path.read_text())
    if config.get("RUNTIME_ENVIRONMENT") != "synthetic":
        raise RuntimeError("Refusing to load synthetic Questrade data into a non-synthetic runtime")

    scenario = read_scenario(scenario_name)
    runtime = RuntimeConfig.load(target)
    initialize_database(runtime.connect)
    with runtime.connect() as connection:
        for connection_name in scenario:
            # Placeholder tokens for the synthetic runtime; never sent to Questrade.
            QuestradeAuthorizationRepository(connection).add_if_absent(
                connection_name,
                access_token="synthetic",  # nosec
                refresh_token="synthetic",
                api_server="https://api01.iq.questrade.com/",
            )

    api = SyntheticQuestradeAPI(scenario)

    def no_refresh(_connection: sqlite3.Connection) -> None:
        return None

    def no_authorization_refresh(
        _connection: sqlite3.Connection, _authorization: QuestradeAuthorization
    ) -> None:
        return None

    results = [
        sync_questrade_connection(
            runtime.connect,
            connection_name,
            api_getter=api,
            refresh_expiring=no_refresh,
            refresh_authorization=no_authorization_refresh,
        )
        for connection_name in sorted(scenario)
    ]

    owner_names = {"primary": "Alex Example", "secondary": "Jordan Example"}
    with runtime.connect() as connection:
        for connection_name, owner_name in owner_names.items():
            owner = PersonRepository(connection).find_by_name(owner_name)
            if not owner or connection_name not in scenario:
                continue
            for account in scenario[connection_name]["accounts"]:
                linked = AccountRepository(connection).find_by_external_id(
                    "questrade", account["number"]
                )
                if linked:
                    AccountOwnershipRepository(connection).replace(linked.id, [(owner.id, 1.0)])
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load invented Questrade data")
    parser.add_argument("data_dir", type=Path)
    parser.add_argument("--scenario", choices=("initial", "updated"), default="initial")
    arguments = parser.parse_args()
    for result in load_synthetic_questrade(arguments.data_dir, arguments.scenario):
        print(json.dumps(result, sort_keys=True))
