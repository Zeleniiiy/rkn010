from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .config import REGISTRY_ENTRY_TYPE, RKN_UNIT
from .models import LicensePlan, SourceRow


def iso_moscow(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%Y-%m-%dT00:00:00.000+0300")


def esnsi_date(value: datetime | None) -> str:
    return value.strftime("%d.%m.%Y г.") if value else ""


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def now_utc_offset() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:23] + "+0000"


def iso_utc_midnight(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%Y-%m-%dT00:00:00.000+0000")


def licence_number_esnsi(row: SourceRow) -> str:
    # Repetitions are intentional and must be preserved.
    return " ".join(
        value
        for value in (row.licence_number_1, row.licence_number_2, row.licence_number_3)
        if value
    )


def build_for_registry(row: SourceRow) -> dict[str, Any]:
    result: dict[str, Any] = {
        "order": [
            {
                "order_num": row.include_order_number,
                "order_date": iso_moscow(row.include_order_date),
                "order_date_ESNSI": esnsi_date(row.include_order_date),
            }
        ],
        "regno": row.regno,
        "geo_zone": int(row.geo_zone),
        "location": row.location,
        "org_name": row.org_name,
        "expertOpinion": (
            [{"opinionDate": iso_moscow(row.expert_opinion_date)}]
            if row.expert_opinion_date
            else []
        ),
        "cancellation": [],
        "short_org_name": row.short_org_name,
        "licenceNumberESNSI": licence_number_esnsi(row),
    }
    for field, value in (
        ("licenceNumber1", row.licence_number_1),
        ("licenceNumber2", row.licence_number_2),
        ("licenceNumber3", row.licence_number_3),
    ):
        if value:
            result[field] = value
    if row.exclude_order_number or row.exclude_order_date:
        result["cancellation"] = [
            {
                "cancellation_num": row.exclude_order_number,
                "cancellation_date": iso_moscow(row.exclude_order_date),
                "cancellation_date_ESNSI": esnsi_date(row.exclude_order_date),
            }
        ]
    return result


def build_license_application_data(row: SourceRow) -> dict[str, dict[str, Any] | None]:
    """Build the three licence dictionary blocks used by licenses and records."""
    result: dict[str, dict[str, Any] | None] = {}
    for slot, number, date_end, _status in row.licence_slots():
        if not number:
            result[slot] = None
            continue
        if date_end is None:
            raise ValueError(
                f"Строка Excel {row.excel_row}: не указана дата окончания {slot} {number!r}"
            )
        result[slot] = {
            "lic_num": number,
            "lic_date_end": date_end.strftime("%Y-%m-%d"),
        }
    return result


def build_record_application_data(row: SourceRow) -> dict[str, Any]:
    result: dict[str, Any] = {
        "geoNumberZoneCode": int(row.geo_zone),
        "localTelephoneServicesOffered": True if row.licence_number_1 else None,
        "fixedIntrazoneServicesOffered": True if row.licence_number_2 else None,
        "intercityOrInternationalServicesOffered": True if row.licence_number_3 else None,
    }
    result.update(build_license_application_data(row))
    return result


def license_valid_to(row: SourceRow) -> str:
    dates = [date_end for _slot, number, date_end, _status in row.licence_slots() if number and date_end]
    if not dates:
        raise ValueError(f"Строка Excel {row.excel_row}: нет сроков окончания лицензий")
    return iso_utc_midnight(min(dates)) or ""


def build_license_payload(plan: LicensePlan, subject: dict[str, Any]) -> dict[str, Any]:
    issued_at = now_utc_offset()
    payload: dict[str, Any] = {
        "guid": str(uuid4()),
        "unit": deepcopy(RKN_UNIT),
        "units": [deepcopy(RKN_UNIT)],
        "number": plan.geo_zone,
        "status": plan.license_status,
        "subject": deepcopy(subject),
        "date": issued_at,
        # The live process uses the entity creation moment as dateIssued and
        # the earliest lic_date_end among the included licence blocks as dateValidTo.
        "dateIssued": issued_at,
        "dateValidTo": license_valid_to(plan.latest),
        "forRegistry": build_for_registry(plan.latest),
        "applicationData": build_license_application_data(plan.latest),
        "historyData": [],
        "dateAnnulled": now_utc() if plan.license_status == "annulled" else None,
        "parentEntries": "RKN010_Licenses",
        "registryEntryType": deepcopy(REGISTRY_ENTRY_TYPE),
    }
    return payload


def build_record_payload(
    row: SourceRow,
    *,
    subject: dict[str, Any],
    license_id: str,
    license_status: str,
    record_status: str,
    license_date_issued: str | None = None,
    license_date_valid_to: str | None = None,
    license_date_annulled: str | None = None,
) -> dict[str, Any]:
    return {
        "guid": str(uuid4()),
        "unit": deepcopy(RKN_UNIT),
        "number": row.geo_zone,
        "status": record_status,
        "subject": deepcopy(subject),
        "licenseId": license_id,
        "objects": [],
        "license": {
            "number": row.geo_zone,
            "status": license_status,
            "dateIssued": license_date_issued,
            "dateValidTo": license_date_valid_to,
            "dateAnnulled": license_date_annulled,
        },
        "licenseDateIssued": license_date_issued,
        "licenseDateValidTo": license_date_valid_to,
        "parentEntries": "RKN010_Records",
        "registryEntryType": deepcopy(REGISTRY_ENTRY_TYPE),
        "operationType": "registration",
        "xsdData": {
            "forRegistry": build_for_registry(row),
            "applicationData": build_record_application_data(row),
        },
    }
