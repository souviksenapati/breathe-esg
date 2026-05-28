from __future__ import annotations

import csv
import io

from django.db import transaction
from rest_framework import mixins, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .ingestion import parse_rows
from .models import (
    AuditAction,
    AuditEvent,
    DataSource,
    DataSourceType,
    IngestionJob,
    IngestionStatus,
    NormalizedRecord,
    RawRecord,
    RawRecordStatus,
    ReviewStatus,
)
from .serializers import (
    AuditEventSerializer,
    IngestionJobSerializer,
    LoginSerializer,
    NormalizedRecordSerializer,
    RawRecordSerializer,
)


class TenantScopedQuerysetMixin:
    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(tenant=self.request.user.tenant)


class LoginView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {
                "token": token.key,
                "user": {"id": user.id, "username": user.username, "tenant": user.tenant.slug},
            }
        )


class IngestionJobViewSet(TenantScopedQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = IngestionJobSerializer

    def get_queryset(self):
        return (
            IngestionJob.objects.select_related("source")
            .filter(tenant=self.request.user.tenant)
            .order_by("-id")
        )

    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def upload(self, request):
        """Upload a CSV file for a given source type.

        Body:
        - source_type: sap|utility|travel
        - file: CSV file
        """

        source_type = (request.data.get("source_type") or "").strip().lower()
        upload = request.FILES.get("file")

        if source_type not in {DataSourceType.SAP, DataSourceType.UTILITY, DataSourceType.TRAVEL}:
            return Response({"error": "Invalid source_type"}, status=status.HTTP_400_BAD_REQUEST)
        if not upload:
            return Response({"error": "Missing file"}, status=status.HTTP_400_BAD_REQUEST)

        tenant = request.user.tenant

        source, _ = DataSource.objects.get_or_create(
            tenant=tenant,
            type=source_type,
            name=f"{source_type}-default",
            defaults={"config": {}},
        )

        with transaction.atomic():
            job = IngestionJob.objects.create(
                tenant=tenant,
                source=source,
                created_by=request.user,
                upload=upload,
                status=IngestionStatus.RECEIVED,
            )
            AuditEvent.objects.create(
                tenant=tenant,
                actor=request.user,
                action=AuditAction.INGESTION_CREATED,
                entity_type="IngestionJob",
                entity_id=str(job.id),
                after={"source_type": source_type, "filename": upload.name},
            )

        upload.seek(0)
        decoded = upload.read().decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(decoded))
        rows = list(reader)

        total = 0
        parsed = 0
        failed = 0
        suspicious = 0

        for idx, row in enumerate(rows, start=2):
            total += 1
            result = list(parse_rows(source_type, [row]))[0]

            if result.normalized is None:
                failed += 1
                RawRecord.objects.create(
                    tenant=tenant,
                    job=job,
                    row_number=idx,
                    payload=row,
                    status=RawRecordStatus.FAILED,
                    errors=result.errors,
                    warnings=result.warnings,
                )
                continue

            parsed += 1
            raw = RawRecord.objects.create(
                tenant=tenant,
                job=job,
                row_number=idx,
                payload=row,
                status=RawRecordStatus.PARSED,
                errors=[],
                warnings=result.warnings,
            )

            normalized = NormalizedRecord.objects.create(
                tenant=tenant,
                job=job,
                raw_record=raw,
                scope=result.normalized["scope"],
                activity_type=result.normalized["activity_type"],
                occurred_on=result.normalized.get("occurred_on"),
                period_start=result.normalized.get("period_start"),
                period_end=result.normalized.get("period_end"),
                quantity=result.normalized.get("quantity"),
                unit=result.normalized.get("unit", ""),
                quantity_normalized=result.normalized.get("quantity_normalized"),
                unit_normalized=result.normalized.get("unit_normalized", ""),
                cost_amount=result.normalized.get("cost_amount"),
                currency=result.normalized.get("currency", ""),
                description=result.normalized.get("description", ""),
                location=result.normalized.get("location", ""),
                vendor=result.normalized.get("vendor", ""),
                origin=result.normalized.get("origin", ""),
                destination=result.normalized.get("destination", ""),
                suspicious=result.normalized.get("suspicious", False),
                suspicious_reasons=result.normalized.get("suspicious_reasons", []),
                review_status=result.normalized.get("review_status", ReviewStatus.PENDING),
                metadata=result.normalized.get("metadata", {}),
            )

            if normalized.suspicious:
                suspicious += 1

            AuditEvent.objects.create(
                tenant=tenant,
                actor=request.user,
                action=AuditAction.RECORD_CREATED,
                entity_type="NormalizedRecord",
                entity_id=str(normalized.id),
                after={
                    "job_id": job.id,
                    "source_type": source_type,
                    "review_status": normalized.review_status,
                },
            )

        job.total_rows = total
        job.parsed_rows = parsed
        job.failed_rows = failed
        job.suspicious_rows = suspicious
        job.status = IngestionStatus.PARSED if failed == 0 else IngestionStatus.FAILED
        job.save(
            update_fields=[
                "total_rows",
                "parsed_rows",
                "failed_rows",
                "suspicious_rows",
                "status",
                "updated_at",
            ]
        )

        return Response(IngestionJobSerializer(job).data, status=status.HTTP_201_CREATED)


class RawRecordViewSet(TenantScopedQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = RawRecordSerializer

    def get_queryset(self):
        qs = RawRecord.objects.select_related("job", "job__source").filter(tenant=self.request.user.tenant)
        job_id = self.request.query_params.get("job")
        status_q = self.request.query_params.get("status")
        if job_id:
            qs = qs.filter(job_id=job_id)
        if status_q:
            qs = qs.filter(status=status_q)
        return qs.order_by("-id")


class NormalizedRecordViewSet(
    TenantScopedQuerysetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = NormalizedRecordSerializer

    def get_queryset(self):
        qs = NormalizedRecord.objects.select_related("job", "job__source", "approved_by").filter(
            tenant=self.request.user.tenant
        )
        job_id = self.request.query_params.get("job")
        review_status = self.request.query_params.get("review_status")
        activity_type = self.request.query_params.get("activity_type")
        if job_id:
            qs = qs.filter(job_id=job_id)
        if review_status:
            qs = qs.filter(review_status=review_status)
        if activity_type:
            qs = qs.filter(activity_type=activity_type)
        return qs.order_by("-id")

    def partial_update(self, request, *args, **kwargs):
        record = self.get_object()
        if record.is_locked:
            return Response({"error": "Record is locked for audit"}, status=status.HTTP_400_BAD_REQUEST)

        before = NormalizedRecordSerializer(record).data
        resp = super().partial_update(request, *args, **kwargs)
        record.refresh_from_db()
        after = NormalizedRecordSerializer(record).data

        AuditEvent.objects.create(
            tenant=request.user.tenant,
            actor=request.user,
            action=AuditAction.RECORD_EDITED,
            entity_type="NormalizedRecord",
            entity_id=str(record.id),
            before=before,
            after=after,
        )
        return resp

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        record = self.get_object()
        if record.is_locked:
            return Response({"error": "Already locked"}, status=status.HTTP_400_BAD_REQUEST)

        record.approve(actor=request.user)
        record.save(update_fields=["review_status", "locked_at", "approved_at", "approved_by", "updated_at"])

        job = record.job
        job.approved_rows = NormalizedRecord.objects.filter(
            tenant=request.user.tenant, job=job, review_status=ReviewStatus.APPROVED
        ).count()
        job.save(update_fields=["approved_rows", "updated_at"])

        AuditEvent.objects.create(
            tenant=request.user.tenant,
            actor=request.user,
            action=AuditAction.RECORD_APPROVED,
            entity_type="NormalizedRecord",
            entity_id=str(record.id),
            after={"approved_at": record.approved_at.isoformat()},
        )

        return Response(NormalizedRecordSerializer(record).data)

    @action(detail=False, methods=["post"])
    def bulk_approve(self, request):
        ids = request.data.get("ids") or []
        if not isinstance(ids, list) or not ids:
            return Response({"error": "ids must be a non-empty list"}, status=status.HTTP_400_BAD_REQUEST)

        tenant = request.user.tenant
        records = list(NormalizedRecord.objects.filter(tenant=tenant, id__in=ids))
        approved = 0
        affected_job_ids: set[int] = set()

        for r in records:
            if r.is_locked:
                continue
            r.approve(actor=request.user)
            r.save(update_fields=["review_status", "locked_at", "approved_at", "approved_by", "updated_at"])
            approved += 1
            affected_job_ids.add(r.job_id)
            AuditEvent.objects.create(
                tenant=tenant,
                actor=request.user,
                action=AuditAction.RECORD_APPROVED,
                entity_type="NormalizedRecord",
                entity_id=str(r.id),
                after={"approved_at": r.approved_at.isoformat()},
            )

        # Refresh approved_rows counter on every affected IngestionJob.
        for job in IngestionJob.objects.filter(tenant=tenant, id__in=affected_job_ids):
            job.approved_rows = NormalizedRecord.objects.filter(
                tenant=tenant, job=job, review_status=ReviewStatus.APPROVED
            ).count()
            job.save(update_fields=["approved_rows", "updated_at"])

        return Response({"approved": approved})


class AuditEventViewSet(TenantScopedQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    """Read-only audit trail, scoped to the requesting user's tenant."""
    serializer_class = AuditEventSerializer

    def get_queryset(self):
        from .models import AuditEvent
        return (
            AuditEvent.objects.select_related("actor")
            .filter(tenant=self.request.user.tenant)
            .order_by("-id")
        )
