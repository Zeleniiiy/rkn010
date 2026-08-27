from __future__ import annotations

from datetime import datetime

import pytest

from rkn010_migration.models import SourceRow


@pytest.fixture
def source_row():
    def factory(**changes):
        values = {
            "excel_row": 4,
            "row_uuid": "src-row-1",
            "source_record_id": "legacy-1",
            "regno": "00000052",
            "ogrn": "1021600000001",
            "org_name": "ПАО ТЕСТОВЫЙ ОПЕРАТОР",
            "short_org_name": "ПАО ТЕСТ",
            "location": "г. Казань",
            "licence_number_1": "3004",
            "licence_number_2": "3004",
            "licence_number_3": "9913",
            "geo_zone": "843",
            "include_order_number": "00000100",
            "include_order_date": datetime(2020, 1, 2),
            "exclude_order_number": "",
            "exclude_order_date": None,
            "expert_opinion_date": None,
        }
        values.update(changes)
        return SourceRow(**values)

    return factory


def full_subject(ogrn: str = "1021600000001", name: str = "ПАО ТЕСТОВЫЙ ОПЕРАТОР"):
    return {
        "data": {"person": {}, "organization": {"ogrn": ogrn, "name": name, "shortName": "ПАО ТЕСТ"}},
        "kind": {
            "name": "Участник",
            "type": "participant",
            "subKind": {"name": "Юридическое лицо", "specialTypeId": "ulApplicant"},
        },
        "header": f"ПАО ТЕСТ, ОГРН: {ogrn}",
        "shortHeader": "ПАО ТЕСТ",
        "specialTypeId": "ulApplicant",
        "entityType": "subjects",
        "parentEntries": "RKN010Appeals.subjects",
    }
