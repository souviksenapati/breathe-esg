from django.contrib import admin

from .models import AuditEvent, DataSource, IngestionJob, NormalizedRecord, RawRecord, Tenant, User


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
	list_display = ("id", "slug", "name", "created_at")
	search_fields = ("slug", "name")


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
	list_display = ("id", "username", "email", "tenant", "is_staff", "is_active")
	list_filter = ("tenant", "is_staff", "is_active")
	search_fields = ("username", "email")


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
	list_display = ("id", "tenant", "type", "name", "created_at")
	list_filter = ("type", "tenant")


@admin.register(IngestionJob)
class IngestionJobAdmin(admin.ModelAdmin):
	list_display = (
		"id",
		"tenant",
		"source",
		"status",
		"total_rows",
		"parsed_rows",
		"failed_rows",
		"suspicious_rows",
		"approved_rows",
		"created_at",
	)
	list_filter = ("status", "source__type", "tenant")


@admin.register(RawRecord)
class RawRecordAdmin(admin.ModelAdmin):
	list_display = ("id", "tenant", "job", "row_number", "status", "created_at")
	list_filter = ("status", "tenant")


@admin.register(NormalizedRecord)
class NormalizedRecordAdmin(admin.ModelAdmin):
	list_display = (
		"id",
		"tenant",
		"job",
		"scope",
		"activity_type",
		"review_status",
		"suspicious",
		"locked_at",
		"created_at",
	)
	list_filter = ("review_status", "activity_type", "scope", "suspicious", "tenant")


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
	list_display = ("id", "tenant", "actor", "action", "entity_type", "entity_id", "created_at")
	list_filter = ("action", "tenant")


# Register your models here.
