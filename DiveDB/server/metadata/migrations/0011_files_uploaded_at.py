# Generated by Django 5.1.1 on 2024-09-06 05:46

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0010_files_start_time"),
    ]

    operations = [
        migrations.AddField(
            model_name="files",
            name="uploaded_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
