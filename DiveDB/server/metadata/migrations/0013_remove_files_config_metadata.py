# Generated by Django 5.1.1 on 2024-09-06 15:10

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0012_files_file"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="files",
            name="config_metadata",
        ),
    ]
