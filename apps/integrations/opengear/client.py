"""Opengear console-server REST API client.

Used to discover what devices are physically present in the lab by
enumerating ports and (optionally) scraping serials/booted status from
console output. Intentionally minimal — extend as needed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class OpengearError(RuntimeError):
    """Raised for any non-2xx response."""


@dataclass
class ConsolePort:
    id: str
    label: str
    mode: str
    connected: bool


class OpengearClient:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        *,
        verify_tls: bool = True,
        timeout: float = 15.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.verify_tls = verify_tls
        self.timeout = timeout
        self._session = requests.Session()
        self._session.verify = verify_tls
        self._token: str | None = None

    @classmethod
    def from_settings(cls) -> "OpengearClient":
        cfg = settings.OPENGEAR
        return cls(
            base_url=cfg["BASE_URL"],
            username=cfg["USERNAME"],
            password=cfg["PASSWORD"],
            verify_tls=cfg["VERIFY_TLS"],
        )

    def login(self) -> None:
        resp = self._session.post(
            f"{self.base_url}/sessions",
            json={"username": self.username, "password": self.password},
            timeout=self.timeout,
        )
        if resp.status_code >= 400:
            raise OpengearError(f"Opengear login failed: {resp.status_code} {resp.text}")
        body = resp.json()
        self._token = body.get("session") or body.get("token")
        if not self._token:
            raise OpengearError(f"Opengear login response missing token: {body}")
        self._session.headers["Authorization"] = f"Token {self._token}"

    def __enter__(self) -> "OpengearClient":
        self.login()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._token = None
        self._session.headers.pop("Authorization", None)

    def list_ports(self) -> list[ConsolePort]:
        if not self._token:
            self.login()
        resp = self._session.get(f"{self.base_url}/ports", timeout=self.timeout)
        if resp.status_code >= 400:
            raise OpengearError(f"Opengear list_ports failed: {resp.status_code} {resp.text}")
        body = resp.json()
        items = body.get("ports") or body.get("data") or []
        return [
            ConsolePort(
                id=str(p.get("id", "")),
                label=p.get("label", ""),
                mode=p.get("mode", ""),
                connected=bool(p.get("connected", False)),
            )
            for p in items
        ]

    def tail_console(self, port_id: str, lines: int = 50) -> str:
        """Return recent console output for a port (best-effort; depends on
        Opengear console logging being enabled).
        """
        if not self._token:
            self.login()
        resp = self._session.get(
            f"{self.base_url}/ports/{port_id}/log",
            params={"lines": lines},
            timeout=self.timeout,
        )
        if resp.status_code >= 400:
            raise OpengearError(
                f"Opengear tail_console failed: {resp.status_code} {resp.text}"
            )
        body = resp.json()
        return body.get("log", "")
