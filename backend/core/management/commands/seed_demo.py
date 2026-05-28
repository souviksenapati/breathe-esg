from __future__ import annotations

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand

from core.models import DataSource, DataSourceType, Tenant, User


class Command(BaseCommand):
    help = "Seed a demo tenant and analyst user for testing."

    def handle(self, *args, **options):
        # --- Tenant ---
        tenant, created = Tenant.objects.get_or_create(
            slug="acme-corp",
            defaults={"name": "Acme Corporation"},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created tenant: {tenant.name}"))
        else:
            self.stdout.write(f"Tenant already exists: {tenant.name}")

        # --- Analyst user ---
        user, created = User.objects.get_or_create(
            username="analyst",
            defaults={
                "email": "analyst@acme-corp.example",
                "password": make_password("demo1234"),
                "tenant": tenant,
                "is_staff": False,
            },
        )
        if not created:
            # Ensure tenant is set even if user pre-existed without one
            user.tenant = tenant
            user.save(update_fields=["tenant"])
            self.stdout.write(f"User already exists: {user.username}")
        else:
            self.stdout.write(self.style.SUCCESS(f"Created user: {user.username} / demo1234"))

        # --- DataSources ---
        for src_type in [DataSourceType.SAP, DataSourceType.UTILITY, DataSourceType.TRAVEL]:
            ds, ds_created = DataSource.objects.get_or_create(
                tenant=tenant,
                type=src_type,
                name=f"{src_type}-default",
                defaults={"config": {}},
            )
            if ds_created:
                self.stdout.write(self.style.SUCCESS(f"Created DataSource: {ds}"))

        self.stdout.write(self.style.SUCCESS("\nDemo seed complete."))
        self.stdout.write("  Login: analyst / demo1234")
        self.stdout.write(f"  Tenant: {tenant.slug}")
