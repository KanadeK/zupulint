from __future__ import annotations

import pytest

from zupulint.config import SUPPORTED_RULE_IDS, validate_config


def test_supported_rule_inventory_is_exact() -> None:
    assert len(SUPPORTED_RULE_IDS) == 26
    assert {"ZP001", "ZP105", "ZP204", "ZP304", "ZP401", "ZP503", "ZP603"} <= (SUPPORTED_RULE_IDS)


def test_configuration_accepts_known_rule_controls() -> None:
    config = validate_config(
        {
            "version": 1,
            "rules": {"disabled": ["ZP602"], "severity": {"ZP103": "info"}},
        }
    )
    assert config["rules"]["disabled"] == ["ZP602"]
    assert config["rules"]["severity"] == {"ZP103": "info"}


@pytest.mark.parametrize("rule_id", ["ZP999", "bad", "ZP01"])
def test_configuration_rejects_unknown_rule_ids(rule_id: str) -> None:
    with pytest.raises(ValueError, match="unknown rule IDs"):
        validate_config({"version": 1, "rules": {"disabled": [rule_id]}})


def test_configuration_rejects_unknown_keys_and_invalid_age_order() -> None:
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        validate_config({"version": 1, "cloud_upload": True})
    with pytest.raises(ValueError, match="minimum_parent_age"):
        validate_config(
            {
                "version": 1,
                "chronology": {
                    "minimum_parent_age": 70,
                    "maximum_maternal_age": 60,
                    "maximum_paternal_age": 90,
                },
            }
        )
