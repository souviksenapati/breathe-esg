from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class TimestampedModel(models.Model):
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		abstract = True


class Tenant(TimestampedModel):
	name = models.CharField(max_length=200)
	slug = models.SlugField(max_length=100, unique=True)

	def __str__(self) -> str:
		return self.name


class User(AbstractUser):
	tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="users", null=True, blank=True)


class DataSourceType(models.TextChoices):
	SAP = "sap", "SAP"
	UTILITY = "utility", "Utility"
	TRAVEL = "travel", "Travel"


class DataSource(TimestampedModel):
	tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="data_sources")
	type = models.CharField(max_length=20, choices=DataSourceType.choices)
	name = models.CharField(max_length=200)
	config = models.JSONField(default=dict, blank=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=["tenant", "type", "name"], name="uniq_source_per_tenant"),
		]

	def __str__(self) -> str:
		return f"{self.tenant.slug}:{self.type}:{self.name}"


class IngestionStatus(models.TextChoices):
	RECEIVED = "received", "Received"
	PARSED = "parsed", "Parsed"
	FAILED = "failed", "Failed"


class IngestionJob(TimestampedModel):
	tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="ingestion_jobs")
	source = models.ForeignKey(DataSource, on_delete=models.PROTECT, related_name="ingestion_jobs")
	created_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="created_ingestion_jobs",
	)

	status = models.CharField(max_length=20, choices=IngestionStatus.choices, default=IngestionStatus.RECEIVED)
	upload = models.FileField(upload_to="uploads/%Y/%m/%d/")

	total_rows = models.PositiveIntegerField(default=0)
	parsed_rows = models.PositiveIntegerField(default=0)
	failed_rows = models.PositiveIntegerField(default=0)
	suspicious_rows = models.PositiveIntegerField(default=0)
	approved_rows = models.PositiveIntegerField(default=0)

	def __str__(self) -> str:
		return f"{self.id} {self.source.type} {self.status}"


class RawRecordStatus(models.TextChoices):
	PARSED = "parsed", "Parsed"
	FAILED = "failed", "Failed"


class RawRecord(TimestampedModel):
	tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="raw_records")
	job = models.ForeignKey(IngestionJob, on_delete=models.CASCADE, related_name="raw_records")

	row_number = models.PositiveIntegerField()
	payload = models.JSONField(default=dict)
	status = models.CharField(max_length=20, choices=RawRecordStatus.choices)
	errors = models.JSONField(default=list, blank=True)
	warnings = models.JSONField(default=list, blank=True)

	class Meta:
		indexes = [
			models.Index(fields=["tenant", "job", "row_number"]),
			models.Index(fields=["tenant", "status"]),
		]


class ScopeCategory(models.TextChoices):
	SCOPE1 = "scope1", "Scope 1"
	SCOPE2 = "scope2", "Scope 2"
	SCOPE3 = "scope3", "Scope 3"


class ActivityType(models.TextChoices):
	FUEL = "fuel", "Fuel"
	PROCUREMENT = "procurement", "Procurement"
	ELECTRICITY = "electricity", "Electricity"
	FLIGHT = "flight", "Flight"
	HOTEL = "hotel", "Hotel"
	GROUND = "ground", "Ground Transport"


class ReviewStatus(models.TextChoices):
	PENDING = "pending", "Pending"
	SUSPICIOUS = "suspicious", "Suspicious"
	APPROVED = "approved", "Approved"


class NormalizedRecord(TimestampedModel):
	tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="normalized_records")
	job = models.ForeignKey(IngestionJob, on_delete=models.CASCADE, related_name="normalized_records")
	raw_record = models.OneToOneField(RawRecord, on_delete=models.CASCADE, related_name="normalized")

	scope = models.CharField(max_length=20, choices=ScopeCategory.choices)
	activity_type = models.CharField(max_length=20, choices=ActivityType.choices)

	occurred_on = models.DateField(null=True, blank=True)
	period_start = models.DateField(null=True, blank=True)
	period_end = models.DateField(null=True, blank=True)

	quantity = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
	unit = models.CharField(max_length=50, blank=True, default="")
	quantity_normalized = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
	unit_normalized = models.CharField(max_length=50, blank=True, default="")

	cost_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
	currency = models.CharField(max_length=10, blank=True, default="")

	description = models.CharField(max_length=500, blank=True, default="")
	location = models.CharField(max_length=200, blank=True, default="")
	vendor = models.CharField(max_length=200, blank=True, default="")

	origin = models.CharField(max_length=10, blank=True, default="")
	destination = models.CharField(max_length=10, blank=True, default="")

	suspicious = models.BooleanField(default=False)
	suspicious_reasons = models.JSONField(default=list, blank=True)

	review_status = models.CharField(max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.PENDING)
	locked_at = models.DateTimeField(null=True, blank=True)
	approved_at = models.DateTimeField(null=True, blank=True)
	approved_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="approved_records",
	)

	metadata = models.JSONField(default=dict, blank=True)

	class Meta:
		indexes = [
			models.Index(fields=["tenant", "review_status"]),
			models.Index(fields=["tenant", "suspicious"]),
			models.Index(fields=["tenant", "activity_type"]),
		]

	@property
	def is_locked(self) -> bool:
		return self.locked_at is not None

	def approve(self, actor: User | None) -> None:
		if self.is_locked:
			return
		self.review_status = ReviewStatus.APPROVED
		self.locked_at = timezone.now()
		self.approved_at = self.locked_at
		self.approved_by = actor


class AuditAction(models.TextChoices):
	INGESTION_CREATED = "ingestion_created", "Ingestion created"
	RECORD_CREATED = "record_created", "Record created"
	RECORD_EDITED = "record_edited", "Record edited"
	RECORD_APPROVED = "record_approved", "Record approved"


class AuditEvent(TimestampedModel):
	tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="audit_events")
	actor = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="audit_events",
	)
	action = models.CharField(max_length=50, choices=AuditAction.choices)

	entity_type = models.CharField(max_length=100)
	entity_id = models.CharField(max_length=100)

	before = models.JSONField(null=True, blank=True)
	after = models.JSONField(null=True, blank=True)

	class Meta:
		indexes = [
			# Audit log is always filtered by tenant and sorted by recency.
			models.Index(fields=["tenant", "created_at"]),
		]
