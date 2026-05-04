"""Bluecat Address Manager REST API v2 client.

Targets the v2 REST API exposed at `/api/v2`. Endpoints used:
  POST /api/v2/sessions                       -> auth, returns token
  GET  /api/v2/configurations                 -> find configuration by name
  GET  /api/v2/{collection}?filter=...        -> generic object lookup
  POST /api/v2/blocks/{id}/nextAvailableNetwork -> reserve next /N from a block
  POST /api/v2/networks/{id}/nextAvailableAddress -> reserve next IP from a network
  PATCH /api/v2/{type}/{id}                   -> update object (name, tags, user defined fields)

Authentication uses a session token returned by POST /sessions, sent as
`Authorization: Basic <token>` per Bluecat REST v2 docs (the token already
encodes the credential pair).

This client is intentionally narrow: it exposes the few operations the ZTP
orchestrator actually needs, behind small, testable methods.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class BluecatError(RuntimeError):
    """Raised for any non-2xx response or unexpected payload."""


@dataclass
class TaggedObject:
    id: str
    type: str
    name: str
    properties: dict[str, Any]


class BluecatClient:
    """Thin wrapper over Bluecat REST API v2.

    Designed to be instantiated per-request/task; not thread-safe across
    sessions. Use `BluecatClient.from_settings()` to build from Django settings.
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        *,
        verify_tls: bool = True,
        default_configuration: str = "Production",
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.verify_tls = verify_tls
        self.default_configuration = default_configuration
        self.timeout = timeout

        self._session = requests.Session()
        self._session.verify = verify_tls
        self._token: str | None = None
        self._configuration_id: int | None = None

    @classmethod
    def from_settings(cls) -> "BluecatClient":
        cfg = settings.BLUECAT
        return cls(
            base_url=cfg["BASE_URL"],
            username=cfg["USERNAME"],
            password=cfg["PASSWORD"],
            verify_tls=cfg["VERIFY_TLS"],
            default_configuration=cfg["DEFAULT_CONFIG"],
        )

    # ------------------------------------------------------------------ auth

    def login(self) -> None:
        url = f"{self.base_url}/sessions"
        resp = self._session.post(
            url,
            json={"username": self.username, "password": self.password},
            timeout=self.timeout,
        )
        if resp.status_code >= 400:
            raise BluecatError(f"Bluecat login failed: {resp.status_code} {resp.text}")
        body = resp.json()
        token = body.get("apiToken") or body.get("token")
        if not token:
            raise BluecatError(f"Bluecat login response missing token: {body}")
        self._token = token
        self._session.headers.update({"Authorization": f"Basic {token}"})

    def logout(self) -> None:
        if not self._token:
            return
        try:
            self._session.delete(f"{self.base_url}/sessions/current", timeout=self.timeout)
        finally:
            self._token = None
            self._session.headers.pop("Authorization", None)

    def __enter__(self) -> "BluecatClient":
        self.login()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.logout()

    # ----------------------------------------------------------------- core

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json: dict | None = None,
    ) -> Any:
        if not self._token:
            self.login()
        url = f"{self.base_url}{path}"
        resp = self._session.request(
            method,
            url,
            params=params,
            json=json,
            timeout=self.timeout,
        )
        if resp.status_code == 401:
            # Token expired — try once more.
            logger.info("Bluecat token expired, refreshing")
            self._token = None
            self.login()
            resp = self._session.request(
                method, url, params=params, json=json, timeout=self.timeout
            )
        if resp.status_code >= 400:
            raise BluecatError(
                f"Bluecat {method} {path} failed: {resp.status_code} {resp.text}"
            )
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    # ------------------------------------------------------ configurations

    def get_configuration_id(self, name: str | None = None) -> int:
        name = name or self.default_configuration
        if self._configuration_id and name == self.default_configuration:
            return self._configuration_id
        body = self._request(
            "GET",
            "/configurations",
            params={"filter": f"name:eq('{name}')"},
        )
        items = body.get("data", []) if isinstance(body, dict) else []
        if not items:
            raise BluecatError(f"Configuration '{name}' not found in Bluecat")
        cid = int(items[0]["id"])
        if name == self.default_configuration:
            self._configuration_id = cid
        return cid

    # ----------------------------------------------------- tagged lookups

    def find_objects_by_tag(
        self,
        tag_group: str,
        tag_name: str | None = None,
        *,
        object_type: str = "networks",
    ) -> list[TaggedObject]:
        """Return objects of `object_type` (e.g. 'networks', 'addresses', 'blocks')
        carrying the named tag(s). Bluecat tag filters in v2 use the
        `tags` query operator.
        """
        if tag_name:
            tag_filter = f"tags:contains('{tag_group}/{tag_name}')"
        else:
            tag_filter = f"tags:startsWith('{tag_group}')"
        body = self._request("GET", f"/{object_type}", params={"filter": tag_filter})
        items = body.get("data", []) if isinstance(body, dict) else []
        return [
            TaggedObject(
                id=str(it["id"]),
                type=it.get("type", object_type.rstrip("s")),
                name=it.get("name", ""),
                properties=it,
            )
            for it in items
        ]

    # ---------------------------------------------------- next-available

    def next_available_address(
        self,
        network_id: str,
        *,
        name: str,
        hostname: str = "",
        user_defined_fields: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Reserve the next available IP from a network and assign it.

        Returns the address object payload (includes `id`, `address`, etc.).
        """
        payload: dict[str, Any] = {
            "name": name,
            "state": "STATIC",
        }
        if hostname:
            payload["hostInfo"] = [{"hostname": hostname}]
        if user_defined_fields:
            payload["userDefinedFields"] = user_defined_fields
        return self._request(
            "POST",
            f"/networks/{network_id}/nextAvailableAddress",
            json=payload,
        )

    def next_available_network(
        self,
        block_id: str,
        *,
        prefix_length: int,
        name: str,
        user_defined_fields: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Reserve the next available subnet of `prefix_length` from a block."""
        payload: dict[str, Any] = {
            "name": name,
            "size": prefix_length,
        }
        if user_defined_fields:
            payload["userDefinedFields"] = user_defined_fields
        return self._request(
            "POST",
            f"/blocks/{block_id}/nextAvailableNetwork",
            json=payload,
        )

    # ---------------------------------------------------- generic update

    def update_object(
        self,
        object_type: str,
        object_id: str,
        *,
        name: str | None = None,
        user_defined_fields: dict[str, str] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if user_defined_fields is not None:
            body["userDefinedFields"] = user_defined_fields
        if tags is not None:
            body["tags"] = tags
        return self._request("PATCH", f"/{object_type}/{object_id}", json=body)

    def annotate_with_device(
        self,
        object_type: str,
        object_id: str,
        *,
        hostname: str,
        interface: str,
    ) -> dict[str, Any]:
        """Tag a Bluecat object with the router hostname and interface
        responsible for it. Used after we hand an IP/network out to a device.
        """
        return self.update_object(
            object_type,
            object_id,
            name=f"{hostname}:{interface}",
            user_defined_fields={
                "ztp_hostname": hostname,
                "ztp_interface": interface,
            },
        )
