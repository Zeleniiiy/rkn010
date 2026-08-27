from __future__ import annotations

from collections import defaultdict

from .models import LicensePlan, SourceRow, ValidationIssue, WorkbookData


def _history_key(row: SourceRow) -> tuple[int, str, int]:
    regno_number = int(row.regno) if row.regno.isdigit() else 10**30
    order_date = row.include_order_date.isoformat() if row.include_order_date else ""
    return regno_number, order_date, row.excel_row


def build_plan(data: WorkbookData) -> list[LicensePlan]:
    grouped: dict[str, list[SourceRow]] = defaultdict(list)
    for row in data.rows:
        grouped[row.license_key].append(row)

    plans: list[LicensePlan] = []
    seen_record_keys: set[str] = set()
    for key, source_rows in grouped.items():
        rows = sorted(source_rows, key=_history_key)
        issues: list[ValidationIssue] = []
        names = {row.org_name.strip().casefold() for row in rows}
        if len(names) > 1:
            issues.append(
                ValidationIssue(
                    "name_conflict",
                    "Одинаковые ОГРН и зона содержат разные полные наименования",
                    rows[0].excel_row,
                )
            )
        for row in rows:
            if row.record_key in seen_record_keys:
                issues.append(
                    ValidationIssue(
                        "duplicate_record_key",
                        f"Повторяется ОГРН+зона+регистрационный номер: {row.record_key}",
                        row.excel_row,
                    )
                )
            seen_record_keys.add(row.record_key)
        latest = rows[-1]
        plans.append(
            LicensePlan(
                key=key,
                ogrn=latest.ogrn,
                geo_zone=latest.geo_zone,
                rows=rows,
                license_status="annulled" if latest.is_annulled else "active",
                issues=issues,
            )
        )
    return sorted(plans, key=lambda item: (item.ogrn, int(item.geo_zone)))
