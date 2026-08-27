from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


LICENSE_COLLECTION = "RKN010_Licenses"
RECORD_COLLECTION = "RKN010_Records"
ORGANIZATION_COLLECTION = "organizations"

REGISTRY_ENTRY_TYPE = {
    "code": "RKN010_02",
    "name": "Ведение реестра операторов связи, занимающих существенное положение",
}

RKN_UNIT = {
    "id": "5fffdfc6cd52b10001dfcd9c",
    "name": "Федеральная служба по надзору в сфере связи, информационных технологий и массовых коммуникаций (Роскомнадзор)",
    "ogrn": "1087746736296",
    "region": {"code": "77", "name": "г. Москва"},
}

# The source workbook does not contain validity dates yet. The mapper already has
# the integration point, but live payloads intentionally omit the fields until the
# customer supplies the columns and confirms their semantics.
ENABLE_LICENSE_VALIDITY_DATES = False


@dataclass(frozen=True)
class RunSettings:
    profile: str
    workbook: Path
    workdir: Path
    execute: bool = False
    resume: bool = True
    operator_mode: bool = False
    strict_org_name: bool = True
    limit: int | None = None
    timeout_seconds: int = 60
    verify_tls: bool = True
    token_file: Path | None = None
    cookie_file: Path | None = None

