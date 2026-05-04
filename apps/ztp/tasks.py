"""Celery tasks for ZTP orchestration.

* `mirror_config_to_git` — push the latest rendered config into a git repo
  for human-readable diff/audit. Toggled via settings.GIT_MIRROR.ENABLED.
* `discover_lab_inventory` — poll Opengear for current console-port state and
  upsert Device rows in DISCOVERED status.
"""

from __future__ import annotations

import logging
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.integrations.opengear import OpengearClient, OpengearError
from apps.inventory.models import Device, DeviceStatus

from .models import GeneratedConfig

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def mirror_config_to_git(self, generated_config_id: int) -> str:
    """Commit the rendered config to a local git repo and (optionally) push.

    Path layout: <GIT_MIRROR_PATH>/<hostname>.cfg
    Commit message: "render: <hostname> by <user> [<config_id>]"
    """
    if not settings.GIT_MIRROR["ENABLED"]:
        return "disabled"

    import git  # GitPython, imported lazily so dev installs without git work

    cfg = GeneratedConfig.objects.select_related("device").get(pk=generated_config_id)
    repo_path = Path(settings.GIT_MIRROR["PATH"])
    repo_path.mkdir(parents=True, exist_ok=True)

    if (repo_path / ".git").exists():
        repo = git.Repo(repo_path)
    else:
        repo = git.Repo.init(repo_path)

    hostname = cfg.device.hostname or cfg.device.serial_number
    target_file = repo_path / f"{hostname}.cfg"
    target_file.write_text(cfg.body)

    repo.index.add([str(target_file.relative_to(repo_path))])
    author = git.Actor(
        settings.GIT_MIRROR["AUTHOR_NAME"], settings.GIT_MIRROR["AUTHOR_EMAIL"]
    )
    commit = repo.index.commit(
        f"render: {hostname} by {cfg.rendered_by or 'system'} [{cfg.pk}]",
        author=author,
        committer=author,
    )
    cfg.git_commit_sha = commit.hexsha
    cfg.save(update_fields=["git_commit_sha"])

    remote_url = settings.GIT_MIRROR.get("REMOTE")
    if remote_url:
        try:
            origin = repo.remote("origin")
        except ValueError:
            origin = repo.create_remote("origin", remote_url)
        try:
            origin.push(refspec="HEAD:refs/heads/main")
        except git.GitCommandError as exc:
            logger.warning("git push failed for %s: %s", hostname, exc)
            raise self.retry(exc=exc)
    return commit.hexsha


@shared_task
def discover_lab_inventory() -> dict[str, int]:
    """Poll Opengear for connected console ports and reconcile Device rows.

    A connected port whose label matches a known serial is upserted as
    DISCOVERED if we haven't seen it; otherwise the staging timestamp is
    refreshed.
    """
    if not settings.OPENGEAR["BASE_URL"]:
        return {"skipped": 1}
    seen = 0
    upserted = 0
    try:
        with OpengearClient.from_settings() as og:
            ports = og.list_ports()
    except OpengearError as exc:
        logger.error("Opengear discovery failed: %s", exc)
        return {"error": 1}

    now = timezone.now()
    for port in ports:
        if not port.connected or not port.label:
            continue
        seen += 1
        # Convention: port label is "<serial>" or "<hostname>:<serial>".
        serial = port.label.split(":")[-1].strip()
        device, created = Device.objects.get_or_create(
            serial_number=serial,
            defaults={
                "device_model_id": _placeholder_device_model_id(),
                "status": DeviceStatus.DISCOVERED,
            },
        )
        device.console_server = settings.OPENGEAR["BASE_URL"]
        device.console_port = port.id
        device.staging_seen_at = now
        device.save(
            update_fields=["console_server", "console_port", "staging_seen_at", "updated_at"]
        )
        if created:
            upserted += 1
    return {"seen": seen, "upserted": upserted}


def _placeholder_device_model_id() -> int | None:
    """Best-effort fallback so discovery doesn't crash when a brand-new
    serial appears without a known model. Operator must edit the row before
    config render. Returns the first DeviceModel id available, or None.
    """
    from apps.inventory.models import DeviceModel

    first = DeviceModel.objects.order_by("pk").values_list("pk", flat=True).first()
    return first
