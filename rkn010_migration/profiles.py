from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    name: str
    base_url: str
    ui_base_url: str
    jwt_url: str
    production: bool = False


PROFILES: dict[str, Profile] = {
    "dev": Profile(
        name="dev",
        base_url="https://iam.torknd-customer.dev.pd15.digitalgov.mtp",
        ui_base_url="https://iam.torknd-customer.dev.pd15.digitalgov.mtp",
        jwt_url="https://iam.torknd-customer.dev.pd15.digitalgov.mtp/jwt/",
    ),
    "psi": Profile(
        name="psi",
        base_url="https://pgs-psi-inner.digitalgov-torknd-psi-common.apps.k8s.prod1.pd40.sol.mtp",
        ui_base_url="https://psi.pgs.gosuslugi.ru",
        jwt_url="https://psi.pgs.gosuslugi.ru/getDebug",
    ),
    "prod": Profile(
        name="prod",
        base_url="http://pgs-prod-inner.digitalgov-torknd-prod1-common.apps.k8s.prod1.pd40.sol.mtp",
        ui_base_url="https://pgs.gosuslugi.ru",
        jwt_url="https://pgs.gosuslugi.ru/getDebug",
        production=True,
    ),
}


def resolve_profile(
    name: str,
    *,
    base_url: str | None = None,
    ui_base_url: str | None = None,
    jwt_url: str | None = None,
) -> Profile:
    if name not in PROFILES and not base_url:
        raise ValueError(f"Unknown profile {name!r}; custom profile requires --base-url")
    base = PROFILES.get(name, Profile(name, "", "", ""))
    return Profile(
        name=name,
        base_url=(base_url or base.base_url).rstrip("/"),
        ui_base_url=(ui_base_url or base.ui_base_url or base_url or "").rstrip("/"),
        jwt_url=(jwt_url or base.jwt_url or "").rstrip("/"),
        production=base.production or name.lower() in {"prod", "production"},
    )

