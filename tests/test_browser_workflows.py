# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Real browser acceptance against an isolated, disposable synthetic runtime."""

import json
import shutil
import subprocess
import threading
from pathlib import Path

from reportlab.pdfgen.canvas import Canvas
from werkzeug.serving import make_server

import app as application
from infrastructure.runtime_config import RuntimeConfig
from localization import LocalizationService
from synthetic_documents import create_synthetic_hydro_qc_statement
from synthetic_runtime import create_synthetic_runtime


def test_primary_workflows_and_rtl_in_real_browser(tmp_path: Path) -> None:
    root = Path(__file__).parents[1]
    runtime_dir = tmp_path / "runtime"
    database, _ = create_synthetic_runtime(runtime_dir)
    runtime = RuntimeConfig.load(runtime_dir)
    application.initialize(runtime)
    app = application.create_app(runtime)
    catalogs = tmp_path / "catalogs"
    shutil.copytree(root / "localization", catalogs)
    registry = json.loads((catalogs / "registry.json").read_text(encoding="utf-8"))
    registry["locales"].append(
        {"code": "ar-XB", "native_name": "Synthetic RTL", "direction": "rtl", "fallback": "fr-CA"}
    )
    (catalogs / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
    (catalogs / "ar-XB").mkdir()
    (catalogs / "ar-XB" / "core.json").write_text(
        json.dumps({"nav": {"summary": "RTL summary"}}), encoding="utf-8"
    )
    app.extensions["localization"] = LocalizationService(catalogs, runtime_dir)
    hydro = create_synthetic_hydro_qc_statement(tmp_path / "synthetic-hydro.pdf")
    tax = tmp_path / "synthetic-ufile.pdf"
    document = Canvas(str(tax))
    document.drawString(40, 780, "Taxpayer: Alex Example")
    document.drawString(40, 760, "Tax return Summary for 2024 taxation year")
    for index, (line, amount) in enumerate(
        [("10100", "123,456.78"), ("30800", "3,200.00"), ("42000", "18,000.00")]
    ):
        document.drawString(400, 720 - 25 * index, line)
        document.drawString(490, 720 - 25 * index, amount)
    document.showPage()
    document.drawString(40, 780, "Quebec return CPP contribution")
    document.drawString(400, 720, "432")
    document.drawString(490, 720, "15,000.00")
    document.save()
    csv = tmp_path / "synthetic-bank.csv"
    csv.write_text(
        "Date,Description,Amount\n2027-07-01,Original English bank evidence,-12.50\n",
        encoding="utf-8",
    )
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        # Fixed local test runner; paths and URL come only from this synthetic fixture.
        result = subprocess.run(  # nosec B603
            [
                "node",
                str(root / "tests" / "browser" / "workflows.mjs"),
                f"http://127.0.0.1:{server.server_port}",
                str(hydro),
                str(csv),
                str(tax),
            ],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=180,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "BROWSER_ACCEPTANCE_PASSED" in result.stdout
        # The browser does not have any production runtime or private document path.
        assert database.is_file()
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
