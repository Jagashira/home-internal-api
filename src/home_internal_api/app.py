from __future__ import annotations

from http import HTTPStatus
from typing import Any, Callable

from .collectors import collect_containers, collect_host, collect_services, collect_summary, dumps_json
from .config import Settings


JsonHandler = Callable[[Settings], dict]
StartResponse = Callable[[str, list[tuple[str, str]]], Any]
WSGIApplication = Callable[[dict[str, Any], StartResponse], list[bytes]]


def create_app(settings: Settings) -> WSGIApplication:
    routes: dict[str, JsonHandler] = {
        "/api/status/health": lambda _settings: {"ok": True},
        "/api/status/summary": collect_summary,
        "/api/status/services": collect_services,
        "/api/status/containers": collect_containers,
        "/api/status/host": collect_host,
    }

    def app(environ: dict[str, Any], start_response: StartResponse) -> list[bytes]:
        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO", "")

        if method != "GET":
            return _json_response(
                start_response,
                HTTPStatus.METHOD_NOT_ALLOWED,
                {"ok": False, "error": {"code": "method_not_allowed", "message": "only GET is supported"}},
            )

        if path not in routes:
            return _json_response(
                start_response,
                HTTPStatus.NOT_FOUND,
                {"ok": False, "error": {"code": "not_found", "message": "endpoint not found"}},
            )

        if settings.internal_api_secret and environ.get("HTTP_X_INTERNAL_API_SECRET") != settings.internal_api_secret:
            return _json_response(
                start_response,
                HTTPStatus.UNAUTHORIZED,
                {"ok": False, "error": {"code": "unauthorized", "message": "invalid internal api secret"}},
            )

        try:
            payload = routes[path](settings)
            return _json_response(start_response, HTTPStatus.OK, payload)
        except Exception:
            return _json_response(
                start_response,
                HTTPStatus.OK,
                {"ok": False, "error": {"code": "internal_error", "message": "collector failed"}},
            )

    return app


def _json_response(start_response: StartResponse, status: HTTPStatus, payload: dict) -> list[bytes]:
    body = dumps_json(payload)
    headers = [
        ("Content-Type", "application/json"),
        ("Content-Length", str(len(body))),
    ]
    start_response(f"{status.value} {status.phrase}", headers)
    return [body]
