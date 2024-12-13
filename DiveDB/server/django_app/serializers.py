from rest_framework import serializers
from ..metadata.models import Loggers, Animals, Deployments, Recordings, Files


class LoggersSerializer(serializers.ModelSerializer):
    class Meta:
        model = Loggers
        fields = "__all__"


class AnimalsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Animals
        fields = "__all__"


class DeploymentsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deployments
        fields = "__all__"


class RecordingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recordings
        fields = "__all__"


class FilesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Files
        fields = "__all__"
