# Generated by Django 5.1 on 2024-08-23 04:59

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0003_alter_loggers_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="loggers",
            name="wiki",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="metadata.loggerswiki",
            ),
        ),
    ]
