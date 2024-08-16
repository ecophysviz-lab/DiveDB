from django.contrib import admin
from .models import (
    Loggers,
    LoggersWiki,
    Animals,
    Deployments,
    AnimalDeployments,
    Recordings,
    Files,
    MediaUpdates,
)

admin.site.register(Loggers)
admin.site.register(LoggersWiki)
admin.site.register(Animals)
admin.site.register(Deployments)
admin.site.register(AnimalDeployments)
admin.site.register(Recordings)
admin.site.register(Files)
admin.site.register(MediaUpdates)
