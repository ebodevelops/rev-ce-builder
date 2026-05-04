from pathlib import Path

from ..base import DeviceDriver, DriverContext, JinjaDriverMixin, register_driver


class CiscoIosXrDriver(JinjaDriverMixin):
    key = "cisco_iosxr"
    template_dir = Path(__file__).parent / "templates"

    def render_config(self, ctx: DriverContext, scenario_template: str) -> str:
        # scenario_template is e.g. "pe-core.cfg.j2" — looked up under template_dir
        return self.render_template(scenario_template, ctx)

    def render_bootfile(self, ctx: DriverContext, *, config_url: str) -> str:
        # IOS-XR ZTP uses Python or shell script as the bootfile. We render a
        # Python ZTP script that handles software upgrade gating + config pull.
        return self.render_template(
            "ztp_bootfile.py.j2",
            DriverContext(
                hostname=ctx.hostname,
                serial_number=ctx.serial_number,
                site_code=ctx.site_code,
                scenario_key=ctx.scenario_key,
                target_software_version=ctx.target_software_version,
                software_image_url=ctx.software_image_url,
                loopback0=ctx.loopback0,
                interfaces=ctx.interfaces,
                extra={**ctx.extra, "config_url": config_url},
            ),
        )


register_driver(CiscoIosXrDriver())
