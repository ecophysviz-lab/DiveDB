from datetime import datetime
from django.contrib import admin

from .models import (
    AnimalDeployments,
    Animals,
    Deployments,
    Files,
    Loggers,
    LoggersWiki,
    MediaUpdates,
    Recordings,
)

admin.site.register(Loggers)
admin.site.register(LoggersWiki)
admin.site.register(Animals)
admin.site.register(Deployments)
admin.site.register(AnimalDeployments)
admin.site.register(Recordings)
admin.site.register(MediaUpdates)


class FileAdmin(admin.ModelAdmin):
    fields = (
        "file",
        "type",
        "recording",
        "start_time",
        "metadata",
    )
    exclude = ("extension", "delta_path", "uploaded_at")

    def save_model(self, request, obj, form, change):
        obj.extension = obj.file.name.split(".")[-1]
        obj.uploaded_at = datetime.now()
        super().save_model(request, obj, form, change)


admin.site.register(Files, FileAdmin)
