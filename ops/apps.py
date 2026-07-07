from django.apps import AppConfig
from django.conf import settings


class OpsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ops"

    def ready(self):
        if settings.ENABLE_SCHEDULER:
            from . import scheduler

            scheduler.start()
