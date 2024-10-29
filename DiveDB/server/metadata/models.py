"""
This module contains the models for the metadata app.
"""

import os
from datetime import datetime
import pytz

from django.contrib.postgres.fields import ArrayField
from django.db import models
from DiveDB.services.utils.storage import OpenStackStorage


class LoggersWiki(models.Model):
    """
    LoggersWiki is a model that contains the metadata for a logger.
    """

    description = models.TextField(null=True, blank=True)
    tags = ArrayField(models.TextField())
    projects = ArrayField(models.TextField())

    class Meta:
        db_table = "Logger_Wikis"
        verbose_name = "Logger Wiki"
        verbose_name_plural = "Logger Wikis"
        app_label = "metadata"


class Loggers(models.Model):
    """
    Loggers is a model that represents a logger attached to diving vertebrates.
    """

    id = models.CharField(primary_key=True)
    wiki = models.OneToOneField(
        LoggersWiki, null=True, blank=True, on_delete=models.CASCADE
    )
    icon_url = models.URLField(max_length=1000, null=True, blank=True)
    serial_no = models.CharField(null=True, blank=True)
    manufacturer = models.CharField(null=True, blank=True)
    manufacturer_name = models.CharField(null=True, blank=True)
    ptt = models.CharField(null=True, blank=True)
    type = models.CharField(null=True, blank=True)
    type_name = models.CharField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    owner = models.CharField(null=True, blank=True)

    class Meta:
        db_table = "Loggers"
        verbose_name = "Logger"
        verbose_name_plural = "Loggers"
        app_label = "metadata"


class Animals(models.Model):
    """
    Animals is a model that represents an animal in a diving project.
    """

    id = models.CharField(primary_key=True)
    project_id = models.CharField()
    common_name = models.CharField()
    scientific_name = models.CharField()
    lab_id = models.CharField(null=True, blank=True)
    birth_year = models.IntegerField(null=True, blank=True)
    sex = models.CharField(null=True, blank=True)
    domain_ids = models.CharField(null=True, blank=True)

    class Meta:
        db_table = "Animals"
        verbose_name = "Animal"
        verbose_name_plural = "Animals"
        app_label = "metadata"


class Deployments(models.Model):
    """
    Deployments is a model that represents a boat trip to collect data.
    """
    # Create a list of tuples with (timezone, timezone)
    timezone_tuples = [(tz, tz) for tz in pytz.all_timezones]
    TIMEZONE_CHOICES = timezone_tuples

    id = models.CharField(primary_key=True)
    domain_deployment_id = models.CharField(null=True, blank=True)
    animal_age_class = models.CharField(null=True, blank=True)
    animal_age = models.IntegerField(null=True, blank=True)
    deployment_type = models.CharField(null=True, blank=True)
    deployment_name = models.CharField()
    rec_date = models.DateField()
    deployment_latitude = models.FloatField(null=True, blank=True)
    deployment_longitude = models.FloatField(null=True, blank=True)
    deployment_location = models.CharField(null=True, blank=True)
    departure_datetime = models.DateTimeField(null=True, blank=True)
    recovery_latitude = models.FloatField(null=True, blank=True)
    recovery_longitude = models.FloatField(null=True, blank=True)
    recovery_location = models.CharField(null=True, blank=True)
    arrival_datetime = models.DateTimeField(null=True, blank=True)
    animal = models.CharField()
    start_time = models.DateTimeField(null=True, blank=True)
    start_time_precision = models.TextField(null=True, blank=True)
    timezone = models.CharField(choices=TIMEZONE_CHOICES)
    notes = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "Deployments"
        verbose_name = "Deployment"
        verbose_name_plural = "Deployments"
        app_label = "metadata"


class AnimalDeployments(models.Model):
    """
    AnimalDeployments is a model that represents an animal within a deployment.
    """

    deployment = models.ForeignKey(Deployments, on_delete=models.CASCADE)
    animal = models.ForeignKey(Animals, on_delete=models.CASCADE)

    class Meta:
        db_table = "Animal_Deployments"
        verbose_name = "Animal Deployment"
        verbose_name_plural = "Animal Deployments"
        app_label = "metadata"


class Recordings(models.Model):
    """
    Recordings is a model that represents a recording of data from a logger.
    """

    PRECISION_CHOICES = [
        ("precise", "Precise"),
        ("approximate", "Approximate"),
    ]
    id = models.CharField(primary_key=True, editable=False)
    name = models.CharField()
    animal_deployment = models.ForeignKey(AnimalDeployments, on_delete=models.CASCADE)
    logger = models.ForeignKey(Loggers, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    actual_start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    start_time_precision = models.CharField(
        null=True, blank=True, choices=PRECISION_CHOICES
    )
    timezone = models.CharField(max_length=32, null=True, blank=True)
    quality = models.CharField(null=True, blank=True)
    attachment_location = models.CharField(null=True, blank=True)
    attachment_type = models.CharField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.id})"

    class Meta:
        db_table = "Recordings"
        verbose_name = "Recording"
        verbose_name_plural = "Recordings"
        app_label = "metadata"

    def save(self, *args, **kwargs):
        if not self.id:
            animal_id = self.animal_deployment.animal.id
            logger_id = self.logger.id
            # Ensure start_time is a datetime object
            if isinstance(self.start_time, str):
                self.start_time = datetime.fromisoformat(self.start_time)
            start_time_str = self.start_time.strftime("%Y%m%d")
            self.id = f"{start_time_str}_{animal_id}_{logger_id}"
        super().save(*args, **kwargs)


class Files(models.Model):
    """
    Files is a model that represents media and data files
    """

    FILE_TYPE_CHOICES = [
        ("media", "Media"),
        ("data", "Data"),
    ]
    extension = models.CharField()
    type = models.CharField(max_length=5, choices=FILE_TYPE_CHOICES)
    delta_path = models.CharField(null=True, blank=True)
    recording = models.ForeignKey(Recordings, on_delete=models.CASCADE)
    metadata = models.JSONField(null=True, blank=True)
    start_time = models.DateTimeField(null=True, blank=True)
    uploaded_at = models.DateTimeField(null=True, blank=True)
    file = models.FileField(
        upload_to=f"{os.getenv('OPENSTACK_FILE_STORAGE_CONTAINER_NAME', 'media')}/",
        # storage=OpenStackStorage(),
    )

    class Meta:
        db_table = "Files"
        verbose_name = "File"
        verbose_name_plural = "Files"
        app_label = "metadata"


class MediaUpdates(models.Model):
    """
    MediaUpdates is a model that represents an update to a media file.
    """

    UPDATE_TYPE_CHOICES = [
        # These need defintion
        ("type1", "Type 1"),
        ("type2", "Type 2"),
    ]
    file = models.ForeignKey(Files, on_delete=models.CASCADE)
    update_type = models.CharField(max_length=10, choices=UPDATE_TYPE_CHOICES)
    update_factor = models.FloatField()

    class Meta:
        db_table = "Media_Updates"
        verbose_name = "Media Update"
        verbose_name_plural = "Media Updates"
        app_label = "metadata"
