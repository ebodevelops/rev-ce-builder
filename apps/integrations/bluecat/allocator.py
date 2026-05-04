"""High-level allocation helpers built on top of the Bluecat client.

These map the ZTP orchestrator's needs (loopbacks, P2P /31s, mgmt IPs) to
Bluecat object lookups + next-available reservations, and write back the
device hostname/interface so IPAM stays in sync.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings

from .client import BluecatClient, BluecatError

logger = logging.getLogger(__name__)


@dataclass
class AllocatedAddress:
    address: str
    prefix_length: int
    bluecat_object_id: str
    bluecat_object_type: str = "addresses"


@dataclass
class AllocatedNetwork:
    network: str
    prefix_length: int
    bluecat_object_id: str
    bluecat_object_type: str = "networks"


class BluecatAllocator:
    """Allocates loopbacks and P2P networks from tagged Bluecat objects.

    Convention:
      * Loopback pool: an `address-block` or `network` tagged with the
        configured loopback tag group (default `ZTP/Loopbacks`).
      * P2P pool: an `address-block` tagged with the configured P2P tag
        group (default `ZTP/P2P-Networks`); we pull a /31 (or configurable
        prefix) per link.
    """

    def __init__(self, client: BluecatClient | None = None) -> None:
        self.client = client or BluecatClient.from_settings()
        self.loopback_tag = settings.BLUECAT["LOOPBACK_TAG_GROUP"]
        self.p2p_tag = settings.BLUECAT["P2P_TAG_GROUP"]

    # context-manager passthrough
    def __enter__(self) -> "BluecatAllocator":
        self.client.login()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.client.logout()

    # ----------------------------------------------------------- loopback

    def allocate_loopback(self, *, hostname: str, role_tag: str | None = None) -> AllocatedAddress:
        candidates = self.client.find_objects_by_tag(
            self.loopback_tag, role_tag, object_type="networks"
        )
        if not candidates:
            raise BluecatError(
                f"No loopback pool found tagged '{self.loopback_tag}"
                f"{('/' + role_tag) if role_tag else ''}'"
            )
        net = candidates[0]
        result = self.client.next_available_address(
            net.id,
            name=f"{hostname}:Loopback0",
            hostname=hostname,
            user_defined_fields={
                "ztp_hostname": hostname,
                "ztp_interface": "Loopback0",
            },
        )
        return AllocatedAddress(
            address=result["address"],
            prefix_length=int(result.get("prefixLength", 32)),
            bluecat_object_id=str(result["id"]),
        )

    # ---------------------------------------------------------------- p2p

    def allocate_p2p(
        self,
        *,
        hostname: str,
        interface: str,
        prefix_length: int = 31,
        peer_label: str | None = None,
    ) -> AllocatedNetwork:
        candidates = self.client.find_objects_by_tag(
            self.p2p_tag, peer_label, object_type="blocks"
        )
        if not candidates:
            raise BluecatError(
                f"No P2P block found tagged '{self.p2p_tag}"
                f"{('/' + peer_label) if peer_label else ''}'"
            )
        block = candidates[0]
        result = self.client.next_available_network(
            block.id,
            prefix_length=prefix_length,
            name=f"{hostname}:{interface}",
            user_defined_fields={
                "ztp_hostname": hostname,
                "ztp_interface": interface,
            },
        )
        return AllocatedNetwork(
            network=result["range"].split("/")[0]
            if "/" in result.get("range", "")
            else result.get("address", ""),
            prefix_length=prefix_length,
            bluecat_object_id=str(result["id"]),
        )
