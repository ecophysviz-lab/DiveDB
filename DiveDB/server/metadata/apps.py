import os

from django.apps import AppConfig

django_prefix = os.environ.get("DJANGO_PREFIX", "DiveDB")


class MetadataConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = f"{django_prefix}.server.metadata"
