from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

from django.utils.timezone import now

from .models import (
    ActivityType,
    DataSourceType,
    NormalizedRecord,
    ReviewStatus,
    ScopeCategory,
)


@dataclass
class ParseResult:
    normalized: dict[str, Any] | None
    errors: list[str]
    warnings: list[str]


def _parse_date(value: str) -> date | None:
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _parse_decimal(value: str) -> Decimal | None:
    value = (value or "").strip()
    if not value:
        return None
    value = value.replace(",", "")
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None


def _norm_unit(unit: str) -> str:
    u = (unit or "").strip().lower()
    return {
        "kwh": "kWh",
        "mwh": "MWh",
        "l": "L",
        "liter": "L",
        "litre": "L",
        "gal": "gal",
        "gallon": "gal",
        "gallons": "gal",
        "km": "km",
        "mi": "mi",
        "miles": "mi",
    }.get(u, unit.strip())


def _convert_quantity(quantity: Decimal | None, unit: str) -> tuple[Decimal | None, str]:
    if quantity is None:
        return None, ""
    u = _norm_unit(unit)

    if u == "MWh":
        return quantity * Decimal("1000"), "kWh"
    if u == "gal":
        return quantity * Decimal("3.78541"), "L"

    if u in {"kWh", "L", "km"}:
        return quantity, u

    return quantity, u


def _suspicious_reasons(record: dict[str, Any]) -> list[str]:
    reasons: list[str] = []

    qn = record.get("quantity_normalized")
    if qn is not None and qn < 0:
        reasons.append("negative_quantity")

    if record.get("activity_type") == ActivityType.FLIGHT and not (
        (record.get("origin") and record.get("destination"))
    ):
        reasons.append("missing_airports")

    if record.get("activity_type") in {ActivityType.ELECTRICITY}:
        if not record.get("period_start") or not record.get("period_end"):
            reasons.append("missing_billing_period")

    if record.get("occurred_on"):
        if record["occurred_on"] > now().date():
            reasons.append("future_date")

    if record.get("unit_normalized") == "":
        reasons.append("missing_unit")

    return reasons


def parse_rows(source_type: str, rows: Iterable[dict[str, str]]) -> Iterable[ParseResult]:
    if source_type == DataSourceType.SAP:
        yield from _parse_sap(rows)
    elif source_type == DataSourceType.UTILITY:
        yield from _parse_utility(rows)
    elif source_type == DataSourceType.TRAVEL:
        yield from _parse_travel(rows)
    else:
        for _ in rows:
            yield ParseResult(normalized=None, errors=["unknown_source_type"], warnings=[])


def _parse_sap(rows: Iterable[dict[str, str]]) -> Iterable[ParseResult]:
    """Prototype: SAP flat export CSV.

    Expected columns (subset, intentionally):
    - record_type: fuel|procurement
    - doc_date
    - quantity, unit (for fuel)
    - amount, currency (for procurement)
    - plant_code
    - material_description / vendor
    """

    for row in rows:
        errors: list[str] = []
        warnings: list[str] = []

        record_type = (row.get("record_type") or "").strip().lower()
        doc_date = _parse_date(row.get("doc_date", ""))

        if record_type not in {"fuel", "procurement"}:
            errors.append("invalid_record_type")

        if not doc_date:
            errors.append("invalid_or_missing_doc_date")

        if errors:
            yield ParseResult(normalized=None, errors=errors, warnings=warnings)
            continue

        if record_type == "fuel":
            quantity = _parse_decimal(row.get("quantity", ""))
            unit = row.get("unit", "")
            qn, un = _convert_quantity(quantity, unit)
            if quantity is None:
                errors.append("missing_quantity")

            normalized: dict[str, Any] = {
                "scope": ScopeCategory.SCOPE1,
                "activity_type": ActivityType.FUEL,
                "occurred_on": doc_date,
                "quantity": quantity,
                "unit": _norm_unit(unit),
                "quantity_normalized": qn,
                "unit_normalized": un,
                "location": (row.get("plant_code") or "").strip(),
                "vendor": (row.get("vendor") or "").strip(),
                "description": (row.get("material_description") or "").strip(),
                "metadata": {
                    "sap_doc": (row.get("sap_doc") or "").strip(),
                },
            }
        else:
            amount = _parse_decimal(row.get("amount", ""))
            currency = (row.get("currency") or "").strip().upper()
            if amount is None:
                errors.append("missing_amount")
            if not currency:
                errors.append("missing_currency")

            normalized = {
                "scope": ScopeCategory.SCOPE3,
                "activity_type": ActivityType.PROCUREMENT,
                "occurred_on": doc_date,
                "cost_amount": amount,
                "currency": currency,
                "location": (row.get("plant_code") or "").strip(),
                "vendor": (row.get("vendor") or "").strip(),
                "description": (row.get("material_description") or "").strip(),
                "metadata": {
                    "po_number": (row.get("po_number") or "").strip(),
                    "gl_account": (row.get("gl_account") or "").strip(),
                },
            }

        if errors:
            yield ParseResult(normalized=None, errors=errors, warnings=warnings)
            continue

        reasons = _suspicious_reasons(normalized)
        normalized["suspicious"] = bool(reasons)
        normalized["suspicious_reasons"] = reasons
        normalized["review_status"] = ReviewStatus.SUSPICIOUS if reasons else ReviewStatus.PENDING

        yield ParseResult(normalized=normalized, errors=[], warnings=warnings)


def _parse_utility(rows: Iterable[dict[str, str]]) -> Iterable[ParseResult]:
    """Prototype: Utility portal CSV export (electricity).

    Expected columns:
    - meter_id
    - period_start, period_end
    - usage
    - unit (kWh|MWh)
    - facility_name
    """

    for row in rows:
        errors: list[str] = []
        warnings: list[str] = []

        meter_id = (row.get("meter_id") or "").strip()
        ps = _parse_date(row.get("period_start", ""))
        pe = _parse_date(row.get("period_end", ""))
        usage = _parse_decimal(row.get("usage", ""))
        unit = row.get("unit", "")

        if not meter_id:
            errors.append("missing_meter_id")
        if not ps or not pe:
            errors.append("invalid_or_missing_period")
        if usage is None:
            errors.append("missing_usage")

        if errors:
            yield ParseResult(normalized=None, errors=errors, warnings=warnings)
            continue

        qn, un = _convert_quantity(usage, unit)

        normalized: dict[str, Any] = {
            "scope": ScopeCategory.SCOPE2,
            "activity_type": ActivityType.ELECTRICITY,
            "period_start": ps,
            "period_end": pe,
            "quantity": usage,
            "unit": _norm_unit(unit),
            "quantity_normalized": qn,
            "unit_normalized": un,
            "location": (row.get("facility_name") or "").strip(),
            "description": f"Meter {meter_id}",
            "metadata": {
                "meter_id": meter_id,
                "tariff": (row.get("tariff") or "").strip(),
            },
        }

        reasons = _suspicious_reasons(normalized)
        normalized["suspicious"] = bool(reasons)
        normalized["suspicious_reasons"] = reasons
        normalized["review_status"] = ReviewStatus.SUSPICIOUS if reasons else ReviewStatus.PENDING

        yield ParseResult(normalized=normalized, errors=[], warnings=warnings)


def _parse_travel(rows: Iterable[dict[str, str]]) -> Iterable[ParseResult]:
    """Prototype: Corporate travel platform CSV export.

    Expected columns:
    - trip_type: flight|hotel|ground
    - booked_date
    - origin, destination (for flight)
    - cost_amount, currency
    - distance, distance_unit (optional)
    """

    for row in rows:
        errors: list[str] = []
        warnings: list[str] = []

        trip_type = (row.get("trip_type") or "").strip().lower()
        booked_date = _parse_date(row.get("booked_date", ""))
        cost_amount = _parse_decimal(row.get("cost_amount", ""))
        currency = (row.get("currency") or "").strip().upper()

        if trip_type not in {"flight", "hotel", "ground"}:
            errors.append("invalid_trip_type")
        if not booked_date:
            errors.append("invalid_or_missing_booked_date")
        if cost_amount is None:
            errors.append("missing_cost_amount")
        if not currency:
            errors.append("missing_currency")

        if errors:
            yield ParseResult(normalized=None, errors=errors, warnings=warnings)
            continue

        if trip_type == "flight":
            activity_type = ActivityType.FLIGHT
        elif trip_type == "hotel":
            activity_type = ActivityType.HOTEL
        else:
            activity_type = ActivityType.GROUND

        distance = _parse_decimal(row.get("distance", ""))
        distance_unit = row.get("distance_unit", "")
        qn, un = _convert_quantity(distance, distance_unit)

        normalized: dict[str, Any] = {
            "scope": ScopeCategory.SCOPE3,
            "activity_type": activity_type,
            "occurred_on": booked_date,
            "cost_amount": cost_amount,
            "currency": currency,
            "origin": (row.get("origin") or "").strip().upper(),
            "destination": (row.get("destination") or "").strip().upper(),
            "quantity": distance,
            "unit": _norm_unit(distance_unit),
            "quantity_normalized": qn,
            "unit_normalized": un,
            "vendor": (row.get("vendor") or "").strip(),
            "description": (row.get("description") or "").strip(),
            "metadata": {
                "ticket_class": (row.get("ticket_class") or "").strip(),
                "trip_id": (row.get("trip_id") or "").strip(),
            },
        }

        reasons = _suspicious_reasons(normalized)
        if distance is None and activity_type in {ActivityType.FLIGHT, ActivityType.GROUND}:
            reasons.append("missing_distance")

        normalized["suspicious"] = bool(reasons)
        normalized["suspicious_reasons"] = reasons
        normalized["review_status"] = ReviewStatus.SUSPICIOUS if reasons else ReviewStatus.PENDING

        yield ParseResult(normalized=normalized, errors=[], warnings=warnings)


def read_csv(path: Path) -> Iterable[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield {k: (v or "") for k, v in row.items()}
