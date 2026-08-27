from __future__ import annotations

from datetime import datetime

from rkn010_migration.mapping import build_for_registry, build_license_payload, build_record_payload
from rkn010_migration.models import LicensePlan

from conftest import full_subject


def test_for_registry_preserves_repeated_licence_numbers(source_row):
    mapped = build_for_registry(source_row())
    assert mapped["licenceNumberESNSI"] == "3004 3004 9913"
    assert mapped["geo_zone"] == 843
    assert mapped["order"][0]["order_date"] == "2020-01-02T00:00:00.000+0300"


def test_annulled_license_still_has_active_latest_record(source_row):
    row = source_row(
        exclude_order_number="00000200",
        exclude_order_date=datetime(2021, 4, 5),
    )
    plan = LicensePlan(row.license_key, row.ogrn, row.geo_zone, [row], "annulled")
    subject = full_subject()
    license_payload = build_license_payload(plan, subject)
    record_payload = build_record_payload(
        row,
        subject=subject,
        license_id="license-1",
        license_status="annulled",
        record_status="active",
    )
    assert license_payload["status"] == "annulled"
    assert license_payload["forRegistry"]["cancellation"][0]["cancellation_num"] == "00000200"
    assert record_payload["status"] == "active"
    assert record_payload["license"]["status"] == "annulled"
    assert record_payload["number"] == "843"
    assert record_payload["xsdData"]["forRegistry"]["regno"] == "00000052"
