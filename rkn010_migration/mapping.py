from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .config import (
    ENABLE_LICENSE_VALIDITY_DATES,
    REGISTRY_ENTRY_TYPE,
    RKN_UNIT,
)
from .models import LicensePlan, SourceRow


def iso_moscow(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%Y-%m-%dT00:00:00.000+0300")


def esnsi_date(value: datetime | None) -> str:
    return value.strftime("%d.%m.%Y г.") if value else ""


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


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


def build_license_payload(plan: LicensePlan, subject: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "guid": str(uuid4()),
        "unit": deepcopy(RKN_UNIT),
        "units": [deepcopy(RKN_UNIT)],
        "number": plan.geo_zone,
        "status": plan.license_status,
        "subject": deepcopy(subject),
        # Validity start is not present in the source workbook. Server-side
        # dateCreation is separate and will be populated by PGS automatically.
        "dateIssued": None,
        "dateValidTo": None,
        "forRegistry": build_for_registry(plan.latest),
        "historyData": [],
        "dateAnnulled": now_utc() if plan.license_status == "annulled" else None,
        "parentEntries": "RKN010_Licenses",
        "registryEntryType": deepcopy(REGISTRY_ENTRY_TYPE),
    }
    if ENABLE_LICENSE_VALIDITY_DATES:
        # TODO(RKN010): map confirmed validity columns here when they are added
        # to the workbook. Do not infer perpetual licenses from an empty date.
        # payload["dateIssued"] = iso_moscow(plan.latest.valid_from)
        # payload["dateValidTo"] = iso_moscow(plan.latest.valid_to)
        raise NotImplementedError("License validity columns are not confirmed")
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
        },
        "parentEntries": "RKN010_Records",
        "registryEntryType": deepcopy(REGISTRY_ENTRY_TYPE),
        "operationType": "registration",
        "xsdData": {"forRegistry": build_for_registry(row)},
    }
