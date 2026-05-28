from __future__ import annotations

from django.contrib.auth import authenticate
from rest_framework import serializers

from .models import AuditEvent, IngestionJob, NormalizedRecord, RawRecord


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()

    def validate(self, attrs):
        user = authenticate(username=attrs["username"], password=attrs["password"])
        if not user:
            raise serializers.ValidationError("Invalid credentials")
        if not getattr(user, "tenant_id", None):
            raise serializers.ValidationError("User is not assigned to a tenant")
        attrs["user"] = user
        return attrs


class IngestionJobSerializer(serializers.ModelSerializer):
    source_type = serializers.CharField(source="source.type", read_only=True)
    source_name = serializers.CharField(source="source.name", read_only=True)

    class Meta:
        model = IngestionJob
        fields = [
            "id",
            "source",
            "source_type",
            "source_name",
            "status",
            "upload",
            "total_rows",
            "parsed_rows",
            "failed_rows",
            "suspicious_rows",
            "approved_rows",
            "created_at",
        ]
        read_only_fields = [
            "status",
            "total_rows",
            "parsed_rows",
            "failed_rows",
            "suspicious_rows",
            "approved_rows",
            "created_at",
        ]


class RawRecordSerializer(serializers.ModelSerializer):
    source_type = serializers.CharField(source="job.source.type", read_only=True)

    class Meta:
        model = RawRecord
        fields = [
            "id",
            "job",
            "source_type",
            "row_number",
            "payload",
            "status",
            "errors",
            "warnings",
            "created_at",
        ]
        read_only_fields = fields


class NormalizedRecordSerializer(serializers.ModelSerializer):
    source_type = serializers.CharField(source="job.source.type", read_only=True)

    class Meta:
        model = NormalizedRecord
        fields = [
            "id",
            "job",
            "source_type",
            "scope",
            "activity_type",
            "occurred_on",
            "period_start",
            "period_end",
            "quantity",
            "unit",
            "quantity_normalized",
            "unit_normalized",
            "cost_amount",
            "currency",
            "description",
            "location",
            "vendor",
            "origin",
            "destination",
            "suspicious",
            "suspicious_reasons",
            "review_status",
            "locked_at",
            "approved_at",
            "approved_by",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "suspicious",
            "suspicious_reasons",
            "locked_at",
            "approved_at",
            "approved_by",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        instance: NormalizedRecord | None = getattr(self, "instance", None)
        if instance and instance.is_locked:
            raise serializers.ValidationError("Record is locked for audit")
        return attrs


class AuditEventSerializer(serializers.ModelSerializer):
    actor = serializers.StringRelatedField()

    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "actor",
            "action",
            "entity_type",
            "entity_id",
            "before",
            "after",
            "created_at",
        ]
        read_only_fields = fields
