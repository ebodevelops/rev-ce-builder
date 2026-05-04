# rev-ce-builder

ZTP orchestration and config builder for MPLS PE routers. Integrates Bluecat
IPAM (REST v2), Opengear console servers, and a per-vendor templating layer
to drive the field-tech → DHCP → ZTP → config-pull → ready workflow.

---

## Prerequisites

- Docker + Docker Compose **or** Python 3.11+, Postgres 16, Redis 7
- Network reachability to Bluecat IPAM and (optionally) Opengear from
  wherever the app runs
- A DHCP server (Kea / ISC) that can hand staging clients an `option 67`
  bootfile-name pointing at this app's `/ztp/bootfile/<serial>` URL

---

## Quick start (Docker Compose)

```bash
git clone <repo-url> rev-ce-builder
cd rev-ce-builder

cp .env.example .env
# edit .env: set DJANGO_SECRET_KEY, BLUECAT_*, OPENGEAR_*, ZTP_PUBLIC_BASE_URL

docker compose build
docker compose up -d

# one-time: apply migrations + create an admin user + seed demo data
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py seed_demo
```

Open <http://localhost:8000> and sign in. The Django admin is at
`/admin/`.

---

## Quick start (local Python, no Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'

# Postgres + Redis must be reachable; defaults assume localhost
createdb ztp                # or: psql -c "CREATE DATABASE ztp;"
cp .env.example .env        # edit DATABASE_URL / REDIS_URL if needed

python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo
python manage.py runserver

# in a second shell:
celery -A config worker -l info
```

---

## Environment variables

All settings are read from `.env` (see `.env.example` for the full list).
Most important ones:

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Required in production |
| `DATABASE_URL` | Postgres DSN, e.g. `postgres://ztp:ztp@db:5432/ztp` |
| `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | Redis endpoints |
| `BLUECAT_BASE_URL` | e.g. `https://bluecat.example.net/api/v2` |
| `BLUECAT_USERNAME` / `BLUECAT_PASSWORD` | Service account creds |
| `BLUECAT_LOOPBACK_TAG_GROUP` | Tag on networks used for loopback allocation (default `ZTP/Loopbacks`) |
| `BLUECAT_P2P_TAG_GROUP` | Tag on blocks used for P2P allocation (default `ZTP/P2P-Networks`) |
| `OPENGEAR_BASE_URL` / `_USERNAME` / `_PASSWORD` | Console-server creds for lab discovery |
| `ZTP_PUBLIC_BASE_URL` | URL devices use to fetch configs/bootfiles (must be reachable from staging VLAN) |
| `ZTP_FILES_ROOT` | On-disk root for `/ztp/images/` (mounted volume `ztp_files` in compose) |
| `GIT_MIRROR_ENABLED` | `True` to commit each rendered config to a git repo for audit |
| `GIT_MIRROR_PATH` | Local path of the mirror repo |
| `GIT_MIRROR_REMOTE` | Optional remote URL to push the mirror to |

---

## Day-to-day workflow

1. **Discover lab inventory** — the `discover_lab_inventory` Celery task
   polls Opengear and upserts `Device` rows in `DISCOVERED` status. Run
   manually or schedule via Celery Beat:

   ```bash
   docker compose exec worker celery -A config call apps.ztp.tasks.discover_lab_inventory
   ```

2. **Reserve a device** — in the web UI (`/`), click *reserve* on the
   target row.

3. **Set hostname / site / scenario** — edit the `Device` in the admin
   (`/admin/inventory/device/`) and assign:
   - `hostname` (e.g. `mpls-rtr-01`)
   - `site` (linked to a `Site`)
   - `scenario` (linked to a `DeploymentScenario` for the device model)

4. **Render the config** — call the API:

   ```bash
   curl -u admin:pw -H 'Content-Type: application/json' \
     -X POST http://localhost:8000/api/ztp/configs/render/ \
     -d '{
           "device_id": 1,
           "interfaces": [
             {"name": "HundredGigE0/0/0/0", "role": "core",
              "peer_label": "core",
              "description": "to-mpls-rtr-02 Hu0/0/0/0"}
           ]
         }'
   ```

   This pulls a loopback + a P2P /31 from Bluecat (using your tagged
   pools), writes the IPs back to Bluecat with the hostname/interface,
   renders the Jinja template, and publishes the result.

5. **Stage the device** — DHCP hands the device an `option 67` of
   `${ZTP_PUBLIC_BASE_URL}/ztp/bootfile/<serial>`. The bootfile script
   captures the SN, upgrades software if older than the model's
   `target_software_version`, fetches `/ztp/configs/<serial>.cfg`,
   applies it, and POSTs to `/ztp/callback/ready/<serial>`.

6. **Watch progress** — the device-detail page shows `ZtpEvent` rows
   in real time as each step happens.

---

## DHCP server configuration

Example Kea snippet for a staging subnet — point `boot-file-name` at the
app's bootfile endpoint, keyed by the device's chassis serial. Kea
substitutes `{client-id}` style macros depending on what your devices
report; for IOS-XR, use the chassis serial supplied via DHCP option 61
or option 124 (vendor class) and template the URL accordingly.

```json
{
  "subnet4": [{
    "subnet": "192.0.2.0/24",
    "pools": [{ "pool": "192.0.2.10 - 192.0.2.200" }],
    "option-data": [
      { "name": "boot-file-name",
        "data": "http://ztp.example.net/ztp/bootfile/<serial>" }
    ]
  }]
}
```

For ISC dhcpd, the equivalent is `option bootfile-name`.

---

## Bluecat setup

The allocator looks up Bluecat objects by tag:

- **Loopback pool** — tag a `network` (e.g. `10.0.0.0/24`) with
  `ZTP/Loopbacks`. The allocator pulls one address per device and writes
  back `name = <hostname>:Loopback0` plus user-defined fields
  `ztp_hostname`, `ztp_interface`.
- **P2P pool** — tag an `address-block` (e.g. `10.1.0.0/16`) with
  `ZTP/P2P-Networks`. The allocator pulls a /31 per interface and writes
  back the same metadata.

You can override either tag via `BLUECAT_LOOPBACK_TAG_GROUP` and
`BLUECAT_P2P_TAG_GROUP`. Sub-tags (e.g. `ZTP/P2P-Networks/core`) let you
have separate pools per interface role; pass `peer_label: "core"` in the
render payload to target them.

---

## Tests

```bash
pytest                       # 9 tests, ~0.5s
pytest tests/test_renderer.py
```

Tests use SQLite + an in-memory DB and stub external HTTP via
`responses`. No Bluecat / Opengear / Redis connectivity is required.

---

## Project layout

```
config/                       Django project (settings, urls, celery)
apps/
  core/                       Shared model mixins
  inventory/                  Device + reservation models, admin, UI, API
  ztp/                        File server, callbacks, render pipeline,
                              Celery tasks, GeneratedConfig + ZtpEvent
  integrations/
    bluecat/                  REST v2 client + allocator
    opengear/                 Console-server client
    devices/
      base.py                 DeviceDriver protocol + Jinja mixin
      cisco_iosxr/            First vendor driver + templates
templates/                    Bootstrap 5 + HTMX server-rendered pages
tests/
```

---

## Production notes

- Switch `DJANGO_SETTINGS_MODULE=config.settings.prod`. This enables HSTS,
  secure cookies, and `X-Frame-Options: DENY`.
- Put the app behind nginx/HAProxy with TLS terminated at the proxy and
  `X-Forwarded-Proto` set so Django sees the request as HTTPS.
- The ZTP endpoints are unauthenticated by default (devices have no creds
  during ZTP). If your staging path is over a tunneled mgmt network you
  can require token auth by setting `ZTP_REQUIRE_AUTH=True` and adding
  the device-side credential.
- Run Celery Beat (already in the compose file) if you want
  `discover_lab_inventory` on a schedule — wire it via Django settings
  `CELERY_BEAT_SCHEDULE`.
- Back up the Postgres volume; it's the source of truth for inventory,
  reservations, and config history.

---

## Adding a new vendor

1. Create `apps/integrations/devices/<key>/__init__.py` defining a
   driver class that implements `render_config()` and
   `render_bootfile()`. Use `JinjaDriverMixin` to inherit the templating
   helpers.
2. Drop templates under `apps/integrations/devices/<key>/templates/`.
3. Register the driver via `register_driver(...)` at module import.
4. Import the module from `apps/integrations/apps.py:ready()` so it
   registers at startup.
5. Create a `Vendor` row with `driver_key=<key>` in admin.
