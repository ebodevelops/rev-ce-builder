from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.integrations"

    def ready(self) -> None:
        # Import drivers so they register themselves
        from .devices import cisco_iosxr  # noqa: F401
