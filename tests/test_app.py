from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from home_internal_api.app import create_app
from home_internal_api.config import Settings


class AppTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings(
            host="home-server",
            port=3010,
            bind_host="127.0.0.1",
            internal_api_secret="secret",
            service_timeout_seconds=1,
            docker_timeout_seconds=1,
            host_timeout_seconds=1,
            monitored_services=["glances"],
            monitored_containers=["news-aggregator"],
            data_disk_path="/",
            root_disk_path="/",
            proc_path="/proc",
            sys_path="/sys",
            docker_socket="unix:///var/run/docker.sock",
            dbus_system_bus_address=None,
        )
        self.app = create_app(self.settings)

    def _request(self, path: str, *, header_secret: str | None = "secret") -> tuple[str, dict]:
        captured: dict[str, object] = {}

        def start_response(status: str, headers: list[tuple[str, str]]) -> None:
            captured["status"] = status
            captured["headers"] = headers

        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": path,
        }
        if header_secret is not None:
            environ["HTTP_X_INTERNAL_API_SECRET"] = header_secret

        body = b"".join(self.app(environ, start_response))
        return captured["status"], json.loads(body.decode("utf-8"))

    def test_health_returns_ok(self) -> None:
        status, payload = self._request("/api/status/health")
        self.assertEqual(status, "200 OK")
        self.assertEqual(payload, {"ok": True})

    def test_requires_secret(self) -> None:
        status, payload = self._request("/api/status/health", header_secret="wrong")
        self.assertEqual(status, "401 Unauthorized")
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "unauthorized")

    def test_unknown_route(self) -> None:
        status, payload = self._request("/missing")
        self.assertEqual(status, "404 Not Found")
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "not_found")


if __name__ == "__main__":
    unittest.main()
