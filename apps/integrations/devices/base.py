"""Vendor-agnostic device driver protocol.

Every supported vendor implements `DeviceDriver`. New vendors register their
driver via `register_driver(key, driver)`; the ZTP renderer/orchestrator looks
up the driver via `get_driver(vendor.driver_key)`.

Templates live under `apps/integrations/devices/<driver_key>/templates/` and
are rendered with Jinja2 from a `DriverContext`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape


@dataclass
class DriverContext:
    """All data a driver needs to render a config + bootfile.

    Drivers should not query the DB or external systems — orchestration code
    populates this and hands it in. This keeps drivers pure and testable.
    """

    hostname: str
    serial_number: str
    site_code: str
    scenario_key: str
    target_software_version: str
    software_image_url: str
    loopback0: str
    interfaces: list[dict[str, Any]] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


class DeviceDriver(Protocol):
    """Protocol every vendor driver implements."""

    key: str
    template_dir: Path

    def render_config(self, ctx: DriverContext, scenario_template: str) -> str: ...

    def render_bootfile(self, ctx: DriverContext, *, config_url: str) -> str: ...


_DRIVERS: dict[str, DeviceDriver] = {}


def register_driver(driver: DeviceDriver) -> None:
    _DRIVERS[driver.key] = driver


def get_driver(key: str) -> DeviceDriver:
    try:
        return _DRIVERS[key]
    except KeyError as exc:
        raise LookupError(f"No device driver registered for '{key}'") from exc


def all_drivers() -> dict[str, DeviceDriver]:
    return dict(_DRIVERS)


class JinjaDriverMixin:
    """Helper for drivers that render Jinja2 templates.

    Subclasses set `template_dir` to a Path. `render_template(name, ctx)`
    returns rendered text with strict undefined-variable handling so a
    missing field fails loudly instead of producing a silently-broken config.
    """

    template_dir: Path

    def _env(self) -> Environment:
        return Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(disabled_extensions=("j2",), default=False),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )

    def render_template(self, template_name: str, ctx: DriverContext) -> str:
        env = self._env()
        template = env.get_template(template_name)
        return template.render(ctx=ctx, **ctx.__dict__)
