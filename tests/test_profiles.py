from __future__ import annotations

import pytest

from rkn010_migration.profiles import resolve_profile


def test_known_profiles_and_prod_guard_flag():
    assert resolve_profile("psi").base_url.startswith("https://")
    assert resolve_profile("prod").production is True


def test_custom_profile_requires_url():
    with pytest.raises(ValueError):
        resolve_profile("demo")
    assert resolve_profile("demo", base_url="https://demo/").base_url == "https://demo"
