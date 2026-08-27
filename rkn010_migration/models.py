from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class SourceRow:
    excel_row: int
    row_uuid: str
    source_record_id: str
    regno: str
    ogrn: str
    org_name: str
    short_org_name: str
    location: str
    licence_number_1: str
    licence_number_2: str
    licence_number_3: str
    geo_zone: str
    include_order_number: str
    include_order_date: datetime | None
    exclude_order_number: str
    exclude_order_date: datetime | None
    expert_opinion_date: datetime | None

    @property
    def license_key(self) -> str:
        return f"{self.ogrn}:{self.geo_zone}"

    @property
    def record_key(self) -> str:
        return f"{self.license_key}:{self.regno}"

    @property
    def is_annulled(self) -> bool:
        return bool(self.exclude_order_number or self.exclude_order_date)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationIssue:
    code: str
    message: str
    excel_row: int | None = None
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LicensePlan:
    key: str
    ogrn: str
    geo_zone: str
    rows: list[SourceRow]
    license_status: str
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def latest(self) -> SourceRow:
        return self.rows[-1]

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "ogrn": self.ogrn,
            "geo_zone": self.geo_zone,
            "license_status": self.license_status,
            "rows": [row.to_dict() for row in self.rows],
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass
class WorkbookData:
    path: str
    sheet_name: str
    rows: list[SourceRow]
    issues: list[ValidationIssue]

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]
