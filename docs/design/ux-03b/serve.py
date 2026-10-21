# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Development-only component showcase. Always creates a disposable synthetic runtime."""

from pathlib import Path
from tempfile import TemporaryDirectory

from flask import Flask, render_template_string
from werkzeug.serving import make_server

import app
from devtools.synthetic.synthetic_runtime import create_synthetic_runtime
from infrastructure.runtime_config import RuntimeConfig


def register_showcase(application: Flask) -> None:
    template = Path(__file__).with_name("index.html").read_text(encoding="utf-8")

    @application.get("/_design-system")
    def showcase():
        return render_template_string(template)


def main() -> None:
    with TemporaryDirectory(prefix="foreview-ux03b-") as directory:
        runtime_dir = Path(directory)
        create_synthetic_runtime(runtime_dir)
        runtime = RuntimeConfig.load(runtime_dir)
        app.initialize(runtime)
        application = app.create_app(runtime)
        register_showcase(application)
        server = make_server("127.0.0.1", 0, application, threaded=True)
        try:
            print(f"http://127.0.0.1:{server.server_port}/_design-system", flush=True)
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == "__main__":
    main()
