"""
URL configuration for django_app project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/

Examples:
    Function views
        1. Add an import:  from my_app import views
        2. Add a URL to urlpatterns:  path('', views.home, name='home')

    Class-based views
        1. Add an import:  from other_app.views import Home
        2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')

    Including another URLconf
        1. Import the include() function: from django.urls import include, path
        2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path
from ..metadata import views

urlpatterns = [
    path("admin/", admin.site.urls),
    # Loggers endpoints
    path("api/loggers/", views.LoggersListView.as_view(), name="loggers-list"),
    path(
        "api/loggers/<int:pk>/",
        views.LoggersRetrieveView.as_view(),
        name="loggers-detail",
    ),
    # Animals endpoints
    path("api/animals/", views.AnimalsListView.as_view(), name="animals-list"),
    path(
        "api/animals/<int:pk>/",
        views.AnimalsRetrieveView.as_view(),
        name="animals-detail",
    ),
    # Deployments endpoints
    path(
        "api/deployments/", views.DeploymentsListView.as_view(), name="deployments-list"
    ),
    path(
        "api/deployments/<int:pk>/",
        views.DeploymentsRetrieveView.as_view(),
        name="deployments-detail",
    ),
    # Recordings endpoints
    path("api/recordings/", views.RecordingsListView.as_view(), name="recordings-list"),
    path(
        "api/recordings/<int:pk>/",
        views.RecordingsRetrieveView.as_view(),
        name="recordings-detail",
    ),
    # Files endpoints
    path("api/files/", views.FilesListView.as_view(), name="files-list"),
    path("api/files/<int:pk>/", views.FilesRetrieveView.as_view(), name="files-detail"),
]
