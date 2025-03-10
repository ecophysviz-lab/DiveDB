"""
WSGI config for django_app project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

django_prefix = os.environ.get("DJANGO_PREFIX", "DiveDB")
os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", f"{django_prefix}.server.django_app.settings"
)

application = get_wsgi_application()
