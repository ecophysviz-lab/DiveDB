"""
This module contains the models for the metadata app.
"""

from django.db import models
from django.contrib.postgres.fields import ArrayField


class LoggersWiki(models.Model):
    """
    LoggersWiki is a model that contains the metadata for a logger.
    """

    description = models.TextField(null=True, blank=True)
    tags = ArrayField(models.TextField())
    projects = ArrayField(models.TextField())

    class Meta:
        verbose_name = "Logger Wiki"
        verbose_name_plural = "Logger Wikis"


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
    type = models.CharField(null=True, blank=True)
    type_name = models.CharField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    owner = models.CharField(null=True, blank=True)

    class Meta:
        verbose_name = "Logger"
        verbose_name_plural = "Loggers"


class Animals(models.Model):
    """
    Animals is a model that represents an animal in a diving project.
    """

    id = models.CharField(primary_key=True)
    project_id = models.CharField()
    common_name = models.CharField()
    scientific_name = models.CharField()

    class Meta:
        verbose_name = "Animal"
        verbose_name_plural = "Animals"


class Deployments(models.Model):
    """
    Deployments is a model that represents a boat trip to collect data.
    """

    TIMEZONE_CHOICES = [
        ("UTC", "UTC"),
        ("US/Pacific", "US/Pacific"),
        ("US/Mountain", "US/Mountain"),
        ("US/Central", "US/Central"),
        ("US/Eastern", "US/Eastern"),
    ]

    id = models.CharField(primary_key=True)
    rec_date = models.DateField()
    animal = models.CharField()
    start_time = models.DateTimeField(null=True, blank=True)
    start_time_precision = models.TextField(null=True, blank=True)
    timezone = models.CharField(max_length=32, choices=TIMEZONE_CHOICES)
    notes = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Deployment"
        verbose_name_plural = "Deployments"


class AnimalDeployments(models.Model):
    """
    AnimalDeployments is a model that represents an animal within a deployment.
    """

    deployment = models.ForeignKey(Deployments, on_delete=models.CASCADE)
    animal = models.ForeignKey(Animals, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Animal Deployment"
        verbose_name_plural = "Animal Deployments"


class Recordings(models.Model):
    """
    Recordings is a model that represents a recording of data from a logger.
    """

    PRECISION_CHOICES = [
        ("precise", "Precise"),
        ("approximate", "Approximate"),
    ]
    id = models.CharField(primary_key=True)
    animal_deployment = models.ForeignKey(AnimalDeployments, on_delete=models.CASCADE)
    logger = models.ForeignKey(Loggers, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    actual_start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    start_time_precision = models.CharField(
        null=True, blank=True, choices=PRECISION_CHOICES
    )

    class Meta:
        verbose_name = "Recording"
        verbose_name_plural = "Recordings"


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
    config_metadata = models.JSONField(null=True, blank=True)
    delta_path = models.CharField(null=True, blank=True)
    file_path = models.CharField(null=True, blank=True)
    recording = models.ForeignKey(Recordings, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "File"
        verbose_name_plural = "Files"


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
        verbose_name = "Media Update"
        verbose_name_plural = "Media Updates"
