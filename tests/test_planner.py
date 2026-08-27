from __future__ import annotations

from datetime import datetime

from rkn010_migration.models import WorkbookData
from rkn010_migration.planner import build_plan


def test_groups_by_ogrn_and_zone_and_sorts_history_by_numeric_regno(source_row):
    newer = source_row(excel_row=4, regno="00000092", include_order_date=datetime(2021, 1, 1))
    older = source_row(excel_row=5, regno="00000052", include_order_date=datetime(2022, 1, 1))
    other_zone = source_row(excel_row=6, regno="00000001", geo_zone="855")
    data = WorkbookData("input.xlsx", "РОСЗСП", [newer, older, other_zone], [])
    plans = build_plan(data)
    assert len(plans) == 2
    zone_843 = next(plan for plan in plans if plan.geo_zone == "843")
    assert [row.regno for row in zone_843.rows] == ["00000052", "00000092"]
    assert zone_843.latest.regno == "00000092"


def test_latest_exclusion_annuls_license_only(source_row):
    older = source_row(regno="1")
    latest = source_row(
        excel_row=5,
        regno="2",
        exclude_order_number="10",
        exclude_order_date=datetime(2022, 1, 1),
    )
    plan = build_plan(WorkbookData("x", "РОСЗСП", [latest, older], []))[0]
    assert plan.license_status == "annulled"

