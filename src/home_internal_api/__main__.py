from __future__ import annotations

from wsgiref.simple_server import make_server

from .app import create_app
from .config import Settings


def main() -> None:
    settings = Settings.from_env()
    app = create_app(settings)

    with make_server(settings.bind_host, settings.port, app) as server:
        print(
            f"home-internal-api listening on http://{settings.bind_host}:{settings.port}",
            flush=True,
        )
        server.serve_forever()


if __name__ == "__main__":
    main()
