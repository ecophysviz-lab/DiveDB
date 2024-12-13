from rest_framework import generics
from .models import Loggers, Animals, Deployments, Recordings, Files
from ..django_app.serializers import (
    LoggersSerializer,
    AnimalsSerializer,
    DeploymentsSerializer,
    RecordingsSerializer,
    FilesSerializer,
)


class LoggersListView(generics.ListAPIView):
    queryset = Loggers.objects.all()
    serializer_class = LoggersSerializer


class LoggersRetrieveView(generics.RetrieveAPIView):
    queryset = Loggers.objects.all()
    serializer_class = LoggersSerializer


class AnimalsListView(generics.ListAPIView):
    queryset = Animals.objects.all()
    serializer_class = AnimalsSerializer


class AnimalsRetrieveView(generics.RetrieveAPIView):
    queryset = Animals.objects.all()
    serializer_class = AnimalsSerializer


class DeploymentsListView(generics.ListAPIView):
    queryset = Deployments.objects.all()
    serializer_class = DeploymentsSerializer


class DeploymentsRetrieveView(generics.RetrieveAPIView):
    queryset = Deployments.objects.all()
    serializer_class = DeploymentsSerializer


class RecordingsListView(generics.ListAPIView):
    queryset = Recordings.objects.all()
    serializer_class = RecordingsSerializer


class RecordingsRetrieveView(generics.RetrieveAPIView):
    queryset = Recordings.objects.all()
    serializer_class = RecordingsSerializer


class FilesListView(generics.ListAPIView):
    queryset = Files.objects.all()
    serializer_class = FilesSerializer


class FilesRetrieveView(generics.RetrieveAPIView):
    queryset = Files.objects.all()
    serializer_class = FilesSerializer
