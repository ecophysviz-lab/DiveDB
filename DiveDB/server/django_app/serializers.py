from rest_framework import serializers
from ..metadata.models import Loggers, Animals, Deployments, Recordings, Files
import numpy as np


class LoggersSerializer(serializers.ModelSerializer):
    class Meta:
        model = Loggers
        fields = "__all__"


class AnimalsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Animals
        fields = "__all__"


class DeploymentsSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        # Get the original representation
        ret = super().to_representation(instance)

        # Replace any NaN values with None
        for field in ret:
            if isinstance(ret[field], float) and np.isnan(ret[field]):
                ret[field] = None

        return ret

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
