# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Opt-in Sage primitives against the real application and disposable facts."""

import importlib.util
import json
import shutil
import subprocess
import threading
from pathlib import Path

from werkzeug.serving import make_server

import app
from devtools.synthetic.synthetic_runtime import create_synthetic_runtime
from infrastructure.runtime_config import RuntimeConfig
from localization import LocalizationService


def test_component_reference_catalogs_match() -> None:
    root = Path(__file__).resolve().parents[1] / "localization"
    catalogs = [
        json.loads((root / locale / "ui_examples.json").read_text(encoding="utf-8"))
        for locale in ("en-CA", "fr-CA")
    ]
    assert catalogs[0].keys() == catalogs[1].keys()
    assert all(
        isinstance(value, str) and value.strip()
        for catalog in catalogs
        for value in catalog.values()
    )


def test_sage_primitives_in_real_browser(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "sage_showcase", root / "docs/design/ux-03b/serve.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    runtime_dir = tmp_path / "runtime"
    create_synthetic_runtime(runtime_dir)
    runtime = RuntimeConfig.load(runtime_dir)
    app.initialize(runtime)
    application = app.create_app(runtime)
    module.register_showcase(application)
    catalogs = tmp_path / "catalogs"
    shutil.copytree(root / "localization", catalogs)
    registry = json.loads((catalogs / "registry.json").read_text(encoding="utf-8"))
    registry["locales"].append(
        {"code": "ar-XB", "native_name": "Synthetic RTL", "direction": "rtl", "fallback": "fr-CA"}
    )
    (catalogs / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
    (catalogs / "ar-XB").mkdir()
    service = LocalizationService(catalogs, runtime_dir)
    application.extensions["localization"] = service
    server = make_server("127.0.0.1", 0, application, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for locale in ("en-CA", "fr-CA", "ar-XB"):
            service.select(locale)
            result = subprocess.run(
                [
                    "node",
                    str(root / "tests/browser/ui-primitives.mjs"),
                    f"http://127.0.0.1:{server.server_port}",
                    locale,
                    str(tmp_path / "evidence"),
                ],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
            assert result.returncode == 0, result.stdout + result.stderr
            assert "SAGE_PRIMITIVES_PASSED" in result.stdout
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_component_showcase_is_not_a_production_route(tmp_path: Path) -> None:
    runtime = RuntimeConfig.load(tmp_path)
    app.initialize(runtime)
    application = app.create_app(runtime)
    assert application.test_client().get("/_design-system").status_code == 404
