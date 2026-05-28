from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AuditEventViewSet,
    IngestionJobViewSet,
    LoginView,
    NormalizedRecordViewSet,
    RawRecordViewSet,
)

router = DefaultRouter()
router.register(r"ingestions", IngestionJobViewSet, basename="ingestion")
router.register(r"records", NormalizedRecordViewSet, basename="record")
router.register(r"raw-records", RawRecordViewSet, basename="raw-record")
router.register(r"audit-events", AuditEventViewSet, basename="audit-event")

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="login"),
    path("", include(router.urls)),
]
