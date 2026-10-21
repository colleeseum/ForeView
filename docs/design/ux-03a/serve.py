# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Disposable synthetic-only servers for this design review, never a private runtime.

From the repository root: PYTHONPATH=. .venv/bin/python docs/design/ux-03a/serve.py
"""

import json
import shutil
import threading
from pathlib import Path
from tempfile import TemporaryDirectory

from flask import Response
from werkzeug.serving import make_server

import app
from devtools.synthetic.synthetic_runtime import create_synthetic_runtime
from infrastructure.runtime_config import RuntimeConfig
from localization import LocalizationService


def synthetic_marker(response: Response) -> Response:
    response.headers["X-ForeView-Audit-Synthetic"] = "1"
    return response


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    servers = []
    with TemporaryDirectory(prefix="foreview-ux03a-") as directory:
        temporary = Path(directory)
        create_synthetic_runtime(temporary / "synthetic")
        catalogs = temporary / "catalogs"
        shutil.copytree(root / "localization", catalogs)
        registry = json.loads((catalogs / "registry.json").read_text(encoding="utf-8"))
        registry["locales"].append(
            {
                "code": "ar-XB",
                "native_name": "Synthetic RTL",
                "direction": "rtl",
                "fallback": "fr-CA",
            }
        )
        (catalogs / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
        (catalogs / "ar-XB").mkdir()
        (catalogs / "ar-XB" / "core.json").write_text("{}", encoding="utf-8")
        urls = {}
        try:
            for name in ("synthetic", "empty"):
                runtime = RuntimeConfig.load(temporary / name)
                app.initialize(runtime)
                application = app.create_app(runtime)
                application.extensions["localization"] = LocalizationService(
                    catalogs, temporary / name
                )
                application.after_request(synthetic_marker)
                server = make_server("127.0.0.1", 0, application, threaded=True)
                servers.append(server)
                threading.Thread(target=server.serve_forever, daemon=True).start()
                urls[name] = f"http://127.0.0.1:{server.server_port}"
            print(json.dumps(urls), flush=True)
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
        finally:
            for server in servers:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    main()
