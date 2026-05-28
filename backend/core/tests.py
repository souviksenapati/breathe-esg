from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from .ingestion import parse_rows, _parse_date, _convert_quantity, _norm_unit
from .models import ActivityType, ReviewStatus, ScopeCategory


# ---------------------------------------------------------------------------
# Helper: collect all ParseResults from parse_rows into a list
# ---------------------------------------------------------------------------

def _parse(source_type: str, rows: list[dict]) -> list:
    return list(parse_rows(source_type, rows))


# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------

class ParseDateTests(TestCase):
    def test_iso_format(self):
        d = _parse_date("2024-01-15")
        self.assertEqual(d.year, 2024)
        self.assertEqual(d.month, 1)
        self.assertEqual(d.day, 15)

    def test_german_format(self):
        """DD.MM.YYYY — common in SAP German-language exports."""
        d = _parse_date("05.02.2024")
        self.assertEqual(d.day, 5)
        self.assertEqual(d.month, 2)

    def test_slash_dmy(self):
        d = _parse_date("14/03/2024")
        self.assertEqual(d.day, 14)
        self.assertEqual(d.month, 3)

    def test_empty_string_returns_none(self):
        self.assertIsNone(_parse_date(""))

    def test_garbage_returns_none(self):
        self.assertIsNone(_parse_date("not-a-date"))


# ---------------------------------------------------------------------------
# Unit conversion
# ---------------------------------------------------------------------------

class ConvertQuantityTests(TestCase):
    def test_mwh_to_kwh(self):
        qty, unit = _convert_quantity(Decimal("195"), "MWh")
        self.assertEqual(qty, Decimal("195000"))
        self.assertEqual(unit, "kWh")

    def test_gal_to_litres(self):
        qty, unit = _convert_quantity(Decimal("100"), "gal")
        self.assertAlmostEqual(float(qty), 378.541, places=2)
        self.assertEqual(unit, "L")

    def test_kwh_passthrough(self):
        qty, unit = _convert_quantity(Decimal("5000"), "kWh")
        self.assertEqual(qty, Decimal("5000"))
        self.assertEqual(unit, "kWh")

    def test_litres_passthrough(self):
        qty, unit = _convert_quantity(Decimal("200"), "L")
        self.assertEqual(qty, Decimal("200"))
        self.assertEqual(unit, "L")

    def test_none_quantity(self):
        qty, unit = _convert_quantity(None, "kWh")
        self.assertIsNone(qty)
        self.assertEqual(unit, "")


# ---------------------------------------------------------------------------
# SAP parser
# ---------------------------------------------------------------------------

class SapParserTests(TestCase):

    FUEL_ROW = {
        "record_type": "fuel",
        "doc_date": "2024-01-10",
        "quantity": "500",
        "unit": "L",
        "plant_code": "DE01",
        "vendor": "Shell",
        "material_description": "Diesel EN590",
        "sap_doc": "4900012345",
        "amount": "",
        "currency": "",
        "po_number": "",
        "gl_account": "",
    }

    PROCUREMENT_ROW = {
        "record_type": "procurement",
        "doc_date": "2024-01-15",
        "quantity": "",
        "unit": "",
        "plant_code": "DE02",
        "vendor": "Würth GmbH",
        "material_description": "Safety equipment",
        "sap_doc": "",
        "amount": "12500.00",
        "currency": "EUR",
        "po_number": "PO-2024-0042",
        "gl_account": "740010",
    }

    def test_fuel_happy_path(self):
        result = _parse("sap", [self.FUEL_ROW])[0]
        self.assertIsNotNone(result.normalized)
        n = result.normalized
        self.assertEqual(n["scope"], ScopeCategory.SCOPE1)
        self.assertEqual(n["activity_type"], ActivityType.FUEL)
        self.assertEqual(n["quantity"], Decimal("500"))
        self.assertEqual(n["unit"], "L")
        self.assertEqual(n["quantity_normalized"], Decimal("500"))
        self.assertEqual(n["unit_normalized"], "L")
        self.assertEqual(n["location"], "DE01")
        self.assertEqual(n["vendor"], "Shell")
        self.assertFalse(n["suspicious"])

    def test_fuel_german_date(self):
        row = {**self.FUEL_ROW, "doc_date": "05.02.2024"}
        result = _parse("sap", [row])[0]
        self.assertIsNotNone(result.normalized)
        self.assertEqual(result.normalized["occurred_on"].month, 2)
        self.assertEqual(result.normalized["occurred_on"].day, 5)

    def test_fuel_negative_quantity_is_suspicious(self):
        row = {**self.FUEL_ROW, "quantity": "-200"}
        result = _parse("sap", [row])[0]
        self.assertIsNotNone(result.normalized)
        self.assertTrue(result.normalized["suspicious"])
        self.assertIn("negative_quantity", result.normalized["suspicious_reasons"])
        self.assertEqual(result.normalized["review_status"], ReviewStatus.SUSPICIOUS)

    def test_fuel_missing_date_is_failed(self):
        row = {**self.FUEL_ROW, "doc_date": ""}
        result = _parse("sap", [row])[0]
        self.assertIsNone(result.normalized)
        self.assertIn("invalid_or_missing_doc_date", result.errors)

    def test_invalid_record_type_fails(self):
        row = {**self.FUEL_ROW, "record_type": "inventory"}
        result = _parse("sap", [row])[0]
        self.assertIsNone(result.normalized)
        self.assertIn("invalid_record_type", result.errors)

    def test_procurement_happy_path(self):
        result = _parse("sap", [self.PROCUREMENT_ROW])[0]
        self.assertIsNotNone(result.normalized)
        n = result.normalized
        self.assertEqual(n["scope"], ScopeCategory.SCOPE3)
        self.assertEqual(n["activity_type"], ActivityType.PROCUREMENT)
        self.assertEqual(n["cost_amount"], Decimal("12500.00"))
        self.assertEqual(n["currency"], "EUR")
        self.assertEqual(n["metadata"]["po_number"], "PO-2024-0042")
        self.assertEqual(n["metadata"]["gl_account"], "740010")
        self.assertFalse(n["suspicious"])

    def test_procurement_missing_amount_fails(self):
        row = {**self.PROCUREMENT_ROW, "amount": ""}
        result = _parse("sap", [row])[0]
        self.assertIsNone(result.normalized)
        self.assertIn("missing_amount", result.errors)

    def test_procurement_missing_currency_fails(self):
        row = {**self.PROCUREMENT_ROW, "currency": ""}
        result = _parse("sap", [row])[0]
        self.assertIsNone(result.normalized)
        self.assertIn("missing_currency", result.errors)

    def test_scope1_for_fuel_scope3_for_procurement(self):
        fuel_result = _parse("sap", [self.FUEL_ROW])[0]
        proc_result = _parse("sap", [self.PROCUREMENT_ROW])[0]
        self.assertEqual(fuel_result.normalized["scope"], ScopeCategory.SCOPE1)
        self.assertEqual(proc_result.normalized["scope"], ScopeCategory.SCOPE3)


# ---------------------------------------------------------------------------
# Utility parser
# ---------------------------------------------------------------------------

class UtilityParserTests(TestCase):

    UTILITY_ROW = {
        "meter_id": "MTR-DE01-A",
        "facility_name": "Frankfurt HQ",
        "period_start": "2024-01-01",
        "period_end": "2024-01-29",
        "usage": "42500",
        "unit": "kWh",
        "tariff": "standard",
    }

    def test_happy_path(self):
        result = _parse("utility", [self.UTILITY_ROW])[0]
        self.assertIsNotNone(result.normalized)
        n = result.normalized
        self.assertEqual(n["scope"], ScopeCategory.SCOPE2)
        self.assertEqual(n["activity_type"], ActivityType.ELECTRICITY)
        self.assertEqual(n["quantity"], Decimal("42500"))
        self.assertEqual(n["unit"], "kWh")
        self.assertEqual(n["quantity_normalized"], Decimal("42500"))
        self.assertEqual(n["unit_normalized"], "kWh")
        self.assertEqual(n["location"], "Frankfurt HQ")
        self.assertEqual(n["metadata"]["meter_id"], "MTR-DE01-A")
        self.assertEqual(n["metadata"]["tariff"], "standard")
        self.assertFalse(n["suspicious"])

    def test_mwh_unit_converted_to_kwh(self):
        """Sample data has one MWh row — must normalise to kWh."""
        row = {**self.UTILITY_ROW, "usage": "195.0", "unit": "MWh"}
        result = _parse("utility", [row])[0]
        self.assertIsNotNone(result.normalized)
        n = result.normalized
        self.assertEqual(n["unit"], "MWh")
        self.assertEqual(n["quantity_normalized"], Decimal("195000.0"))
        self.assertEqual(n["unit_normalized"], "kWh")

    def test_missing_usage_fails(self):
        """Last row of utility_sample.csv intentionally has no usage."""
        row = {**self.UTILITY_ROW, "usage": ""}
        result = _parse("utility", [row])[0]
        self.assertIsNone(result.normalized)
        self.assertIn("missing_usage", result.errors)

    def test_missing_meter_id_fails(self):
        row = {**self.UTILITY_ROW, "meter_id": ""}
        result = _parse("utility", [row])[0]
        self.assertIsNone(result.normalized)
        self.assertIn("missing_meter_id", result.errors)

    def test_missing_period_flags_error(self):
        row = {**self.UTILITY_ROW, "period_start": "", "period_end": ""}
        result = _parse("utility", [row])[0]
        self.assertIsNone(result.normalized)
        self.assertIn("invalid_or_missing_period", result.errors)

    def test_billing_period_stored_separately(self):
        """period_start/period_end must be set; occurred_on must NOT be set."""
        result = _parse("utility", [self.UTILITY_ROW])[0]
        n = result.normalized
        self.assertIsNotNone(n["period_start"])
        self.assertIsNotNone(n["period_end"])
        self.assertNotIn("occurred_on", n)

    def test_negative_usage_is_suspicious(self):
        row = {**self.UTILITY_ROW, "usage": "-100"}
        result = _parse("utility", [row])[0]
        self.assertIsNotNone(result.normalized)
        self.assertTrue(result.normalized["suspicious"])
        self.assertIn("negative_quantity", result.normalized["suspicious_reasons"])

    def test_scope_is_scope2(self):
        result = _parse("utility", [self.UTILITY_ROW])[0]
        self.assertEqual(result.normalized["scope"], ScopeCategory.SCOPE2)


# ---------------------------------------------------------------------------
# Travel parser
# ---------------------------------------------------------------------------

class TravelParserTests(TestCase):

    FLIGHT_ROW = {
        "trip_id": "TRIP-001",
        "trip_type": "flight",
        "booked_date": "2024-01-08",
        "origin": "FRA",
        "destination": "JFK",
        "distance": "6200",
        "distance_unit": "km",
        "cost_amount": "1450.00",
        "currency": "EUR",
        "vendor": "Lufthansa",
        "ticket_class": "Economy",
        "description": "NYC Strategy Summit",
    }

    HOTEL_ROW = {
        "trip_id": "TRIP-001",
        "trip_type": "hotel",
        "booked_date": "2024-01-08",
        "origin": "",
        "destination": "",
        "distance": "3",
        "distance_unit": "",
        "cost_amount": "850.00",
        "currency": "EUR",
        "vendor": "Marriott Times Square",
        "ticket_class": "",
        "description": "NYC hotel 3 nights",
    }

    GROUND_ROW = {
        "trip_id": "TRIP-001",
        "trip_type": "ground",
        "booked_date": "2024-01-10",
        "origin": "",
        "destination": "",
        "distance": "45",
        "distance_unit": "km",
        "cost_amount": "65.00",
        "currency": "EUR",
        "vendor": "NYC Taxi",
        "ticket_class": "",
        "description": "Airport transfer",
    }

    def test_flight_happy_path(self):
        result = _parse("travel", [self.FLIGHT_ROW])[0]
        self.assertIsNotNone(result.normalized)
        n = result.normalized
        self.assertEqual(n["scope"], ScopeCategory.SCOPE3)
        self.assertEqual(n["activity_type"], ActivityType.FLIGHT)
        self.assertEqual(n["origin"], "FRA")
        self.assertEqual(n["destination"], "JFK")
        self.assertEqual(n["quantity"], Decimal("6200"))
        self.assertEqual(n["quantity_normalized"], Decimal("6200"))
        self.assertEqual(n["unit_normalized"], "km")
        self.assertEqual(n["metadata"]["ticket_class"], "Economy")
        self.assertFalse(n["suspicious"])

    def test_flight_missing_distance_is_suspicious(self):
        """travel_sample.csv has two intentional missing-distance rows."""
        row = {**self.FLIGHT_ROW, "distance": ""}
        result = _parse("travel", [row])[0]
        self.assertIsNotNone(result.normalized)
        self.assertTrue(result.normalized["suspicious"])
        self.assertIn("missing_distance", result.normalized["suspicious_reasons"])
        self.assertEqual(result.normalized["review_status"], ReviewStatus.SUSPICIOUS)

    def test_flight_missing_airports_is_suspicious(self):
        row = {**self.FLIGHT_ROW, "origin": "", "destination": ""}
        result = _parse("travel", [row])[0]
        self.assertIsNotNone(result.normalized)
        self.assertTrue(result.normalized["suspicious"])
        self.assertIn("missing_airports", result.normalized["suspicious_reasons"])

    def test_hotel_happy_path(self):
        result = _parse("travel", [self.HOTEL_ROW])[0]
        self.assertIsNotNone(result.normalized)
        n = result.normalized
        self.assertEqual(n["activity_type"], ActivityType.HOTEL)
        self.assertEqual(n["scope"], ScopeCategory.SCOPE3)
        self.assertEqual(n["cost_amount"], Decimal("850.00"))

    def test_ground_happy_path(self):
        result = _parse("travel", [self.GROUND_ROW])[0]
        self.assertIsNotNone(result.normalized)
        n = result.normalized
        self.assertEqual(n["activity_type"], ActivityType.GROUND)
        self.assertEqual(n["quantity"], Decimal("45"))
        self.assertEqual(n["unit_normalized"], "km")

    def test_invalid_trip_type_fails(self):
        row = {**self.FLIGHT_ROW, "trip_type": "train"}
        result = _parse("travel", [row])[0]
        self.assertIsNone(result.normalized)
        self.assertIn("invalid_trip_type", result.errors)

    def test_missing_cost_fails(self):
        row = {**self.FLIGHT_ROW, "cost_amount": ""}
        result = _parse("travel", [row])[0]
        self.assertIsNone(result.normalized)
        self.assertIn("missing_cost_amount", result.errors)

    def test_missing_currency_fails(self):
        row = {**self.FLIGHT_ROW, "currency": ""}
        result = _parse("travel", [row])[0]
        self.assertIsNone(result.normalized)
        self.assertIn("missing_currency", result.errors)

    def test_missing_date_fails(self):
        row = {**self.FLIGHT_ROW, "booked_date": ""}
        result = _parse("travel", [row])[0]
        self.assertIsNone(result.normalized)
        self.assertIn("invalid_or_missing_booked_date", result.errors)

    def test_scope3_for_all_travel_types(self):
        for row in [self.FLIGHT_ROW, self.HOTEL_ROW, self.GROUND_ROW]:
            result = _parse("travel", [row])[0]
            self.assertIsNotNone(result.normalized, msg=f"Expected success for {row['trip_type']}")
            self.assertEqual(result.normalized["scope"], ScopeCategory.SCOPE3)

    def test_ground_missing_distance_is_suspicious(self):
        row = {**self.GROUND_ROW, "distance": ""}
        result = _parse("travel", [row])[0]
        self.assertIsNotNone(result.normalized)
        self.assertTrue(result.normalized["suspicious"])
        self.assertIn("missing_distance", result.normalized["suspicious_reasons"])

    def test_unknown_source_type_yields_error(self):
        result = _parse("unknown_source", [{"foo": "bar"}])[0]
        self.assertIsNone(result.normalized)
        self.assertIn("unknown_source_type", result.errors)

    def test_origin_destination_uppercased(self):
        """IATA codes must be uppercase regardless of input."""
        row = {**self.FLIGHT_ROW, "origin": "fra", "destination": "jfk"}
        result = _parse("travel", [row])[0]
        self.assertEqual(result.normalized["origin"], "FRA")
        self.assertEqual(result.normalized["destination"], "JFK")
