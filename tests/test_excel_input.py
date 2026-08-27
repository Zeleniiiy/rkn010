from __future__ import annotations

from datetime import datetime

from openpyxl import Workbook

from rkn010_migration.excel_input import read_workbook


HEADERS = [
    "row_uuid",
    "Идентификатор записи",
    "Регистрационный номер",
    "ОГРН",
    "Полное наименование",
    "Сокращенное наименование",
    "Место нахождения",
    "N1",
    "N2",
    "N3",
    "Зона нумерации",
    "Номер приказа о включении",
    "Дата приказа о включении",
    "Номер приказа об исключении",
    "Дата приказа об исключении",
    "Дата экспертного заключения",
]


def make_book(path, *, zone="843"):
    wb = Workbook()
    ws = wb.active
    ws.title = "РОСЗСП"
    ws.append(["Таблица миграции"])
    ws.append([])
    ws.append(HEADERS)
    ws.append(
        [
            "uuid",
            "legacy",
            "00000052",
            "1021600000001",
            "ПАО ТЕСТОВЫЙ ОПЕРАТОР",
            "ПАО ТЕСТ",
            "г. Казань",
            "3004",
            "3004",
            "9913",
            zone,
            "00000100",
            datetime(2020, 1, 2),
            "",
            "",
            "",
        ]
    )
    wb.save(path)


def test_reads_current_workbook_layout_and_keeps_identifiers_as_text(tmp_path):
    path = tmp_path / "input.xlsx"
    make_book(path)
    data = read_workbook(path)
    assert not data.errors
    assert data.sheet_name == "РОСЗСП"
    assert data.rows[0].regno == "00000052"
    assert data.rows[0].include_order_number == "00000100"
    assert data.rows[0].include_order_date == datetime(2020, 1, 2)


def test_rejects_compound_numbering_zone(tmp_path):
    path = tmp_path / "input.xlsx"
    make_book(path, zone="843;855")
    data = read_workbook(path)
    assert any(issue.code == "geo_zone_format" for issue in data.errors)

