# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""The design-review launcher can only create disposable local audit runtimes."""

import importlib.util
import json
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask, Response
from werkzeug.serving import make_server


@pytest.fixture
def launcher():
    path = Path(__file__).resolve().parents[1] / "docs/design/ux-03a/serve.py"
    spec = importlib.util.spec_from_file_location("ux03_audit_launcher", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_audit_marker_preserves_response(launcher):
    response = Response("synthetic", status=201)
    assert launcher.synthetic_marker(response) is response
    assert response.headers["X-ForeView-Audit-Synthetic"] == "1"
    assert response.status_code == 201


@pytest.mark.parametrize("fail_second_server", [False, True])
def test_audit_servers_are_local_temporary_and_cleaned(
    launcher, monkeypatch, capsys, fail_second_server
):
    created = []
    applications = []
    destinations = []
    original_create = launcher.create_synthetic_runtime

    def create(path):
        destinations.append(path)
        return original_create(path)

    def server(host, port, application, *, threaded):
        assert host == "127.0.0.1"
        assert port == 0
        assert threaded is True
        if fail_second_server and created:
            raise RuntimeError("Synthetic server startup failure")
        instance = SimpleNamespace(
            server_port=58000 + len(created),
            serve_forever=Mock(),
            shutdown=Mock(),
            server_close=Mock(),
        )
        created.append(instance)
        applications.append(application)
        response = application.test_client().get("/")
        assert response.headers["X-ForeView-Audit-Synthetic"] == "1"
        return instance

    monkeypatch.setattr(launcher, "create_synthetic_runtime", create)
    monkeypatch.setattr(launcher, "make_server", server)
    monkeypatch.setattr(launcher.threading, "Thread", Mock())
    monkeypatch.setattr(
        launcher.threading,
        "Event",
        lambda: SimpleNamespace(wait=Mock(side_effect=KeyboardInterrupt)),
    )
    if fail_second_server:
        with pytest.raises(RuntimeError, match="Synthetic server startup failure"):
            launcher.main()
    else:
        launcher.main()
        urls = json.loads(capsys.readouterr().out)
        assert urls == {
            "synthetic": "http://127.0.0.1:58000",
            "empty": "http://127.0.0.1:58001",
        }
        assert len(applications) == 2
    assert created
    assert len(destinations) == 1
    assert not destinations[0].parent.exists()
    for instance in created:
        instance.shutdown.assert_called_once()
        instance.server_close.assert_called_once()


def test_capture_rejects_page_exception_before_publishing_evidence(launcher, tmp_path):
    application = Flask("synthetic-failed-capture")
    application.after_request(launcher.synthetic_marker)

    @application.get("/")
    def index():
        return "<script>throw new Error('Synthetic browser exception')</script>"

    server = make_server("127.0.0.1", 0, application, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    root = Path(__file__).resolve().parents[1]
    url = f"http://127.0.0.1:{server.server_port}"
    output = tmp_path / "evidence"
    try:
        result = subprocess.run(
            ["node", str(root / "docs/design/ux-03a/capture.mjs"), url, url, str(output)],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode != 0
        assert "Browser exceptions invalidate the capture" in result.stderr
        assert "Synthetic browser exception" in result.stderr
        assert not (output / "measurements.json").exists()
        assert not list(output.glob("*.png"))
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
