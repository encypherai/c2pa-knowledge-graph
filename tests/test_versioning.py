"""Tests for the versioning manager."""

from __future__ import annotations

import pytest

from c2pa_kg.models import SpecVersion
from c2pa_kg.versioning.manager import SPEC_VERSIONS, get_version, list_versions


class TestListVersions:
    def test_returns_list(self) -> None:
        versions = list_versions()
        assert isinstance(versions, list)

    def test_returns_12_versions(self) -> None:
        versions = list_versions()
        assert len(versions) == 12, (
            f"Expected 12 versions, got {len(versions)}: "
            f"{[v.version for v in versions]}"
        )

    def test_all_items_are_spec_version(self) -> None:
        versions = list_versions()
        for v in versions:
            assert isinstance(v, SpecVersion)

    def test_versions_have_non_empty_version_strings(self) -> None:
        versions = list_versions()
        for v in versions:
            assert v.version, f"Empty version string: {v}"

    def test_versions_have_dates(self) -> None:
        versions = list_versions()
        for v in versions:
            assert v.date, f"Missing date for version {v.version}"

    def test_24_is_first(self) -> None:
        # The list is defined newest-first
        versions = list_versions()
        assert versions[0].version == "2.4"

    def test_returns_copy(self) -> None:
        v1 = list_versions()
        v2 = list_versions()
        assert v1 is not v2


class TestGetVersion:
    def test_get_24_returns_correct_version(self) -> None:
        sv = get_version("2.4")
        assert sv.version == "2.4"
        assert sv.tag == "2.4"
        assert sv.date == "2026-04-01"

    def test_get_10_returns_correct_version(self) -> None:
        sv = get_version("1.0")
        assert sv.version == "1.0"

    def test_get_all_registered_versions(self) -> None:
        for sv in SPEC_VERSIONS:
            result = get_version(sv.version)
            assert result.version == sv.version

    def test_get_unknown_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            get_version("9.9")

    def test_get_empty_string_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            get_version("")

    def test_get_wrong_format_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            get_version("v2.4")

    def test_returned_spec_version_has_tag(self) -> None:
        sv = get_version("2.4")
        assert sv.tag, "tag should be non-empty"

    def test_spec_versions_registry_has_12_items(self) -> None:
        assert len(SPEC_VERSIONS) == 12
