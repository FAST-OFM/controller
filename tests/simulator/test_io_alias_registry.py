from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.domain.io_aliases.errors import IoAliasRegistryError  # noqa: E402
from scanner_firmware.domain.io_aliases.loader import (  # noqa: E402
    load_io_alias_registry_from_mapping,
)


FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "io_alias_registry_kingroon_mono_v2_v1.yaml"


def fixture_mapping() -> dict[str, object]:
    payload = yaml.safe_load(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


class IoAliasRegistryTests(unittest.TestCase):
    def test_loads_current_candidate_aliases_from_config_fixture(self):
        registry = load_io_alias_registry_from_mapping(fixture_mapping())

        self.assertEqual(registry.board_id, "kingroon_mono_v2")
        self.assertFalse(registry.hardware_outputs_armed)
        self.assertEqual(
            [(entry.name, entry.pin.raw, entry.status) for entry in registry.candidates()],
            [
                ("camera_or_sync_trigger", "PD6", "candidate"),
                ("led_green", "PA9", "candidate"),
                ("led_red", "PA10", "candidate"),
                ("led_white", "PB13", "candidate"),
            ],
        )
        self.assertEqual(registry.rejected_active_pin_keys, ("PC4", "PD3", "!PB3", "PB1"))

    def test_unknown_output_states_remain_unknown_unless_declared(self):
        registry = load_io_alias_registry_from_mapping(fixture_mapping())

        trigger = registry.get("camera_or_sync_trigger")
        green = registry.get("led_green")
        white = registry.get("led_white")

        self.assertEqual(trigger.output_state.active_value, "unknown")
        self.assertEqual(trigger.output_state.inactive_value, "unknown")
        self.assertEqual(green.output_state.active_value, "unknown")
        self.assertEqual(green.output_state.inactive_value, "unknown")
        self.assertEqual(white.output_state.active_value, 1)
        self.assertEqual(white.output_state.inactive_value, 0)

    def test_preserves_inverted_rejected_pin_reference(self):
        registry = load_io_alias_registry_from_mapping(fixture_mapping())

        inverted = registry.rejected_active_pins[2].pin

        self.assertEqual(inverted.raw, "!PB3")
        self.assertEqual(inverted.name, "PB3")
        self.assertTrue(inverted.inverted)
        self.assertEqual(inverted.key, "!PB3")
        self.assertEqual(inverted.physical_key, "PB3")

    def test_rejects_superseded_pins_as_active_aliases_without_re_review(self):
        for pin in ("PC4", "PD3", "!PB3", "PB3", "PB1"):
            with self.subTest(pin=pin):
                data = fixture_mapping()
                alias = _alias(data, "led_green")
                alias["status"] = "active"
                alias["pin"] = pin

                with self.assertRaisesRegex(IoAliasRegistryError, "uses rejected pin"):
                    load_io_alias_registry_from_mapping(data)

    def test_allows_superseded_pin_only_with_explicit_active_re_review_marker(self):
        data = fixture_mapping()
        alias = _alias(data, "led_green")
        alias["status"] = "active"
        alias["pin"] = "PD3"
        alias["active_alias_reviewed"] = True
        alias["evidence"] = "explicit_re_reviewed_active_alias"

        registry = load_io_alias_registry_from_mapping(data)

        self.assertEqual(registry.active("led_green").pin.raw, "PD3")

    def test_candidate_alias_is_not_resolved_as_active_output(self):
        registry = load_io_alias_registry_from_mapping(fixture_mapping())

        with self.assertRaisesRegex(IoAliasRegistryError, "not active"):
            registry.active("led_white")

    def test_rejects_duplicate_alias_names_unknown_fields_and_bad_values(self):
        data = fixture_mapping()
        duplicate = copy.deepcopy(_alias(data, "led_green"))
        aliases = data["aliases"]
        assert isinstance(aliases, list)
        aliases.append(duplicate)
        with self.assertRaisesRegex(IoAliasRegistryError, "duplicate IO alias"):
            load_io_alias_registry_from_mapping(data)

        data = fixture_mapping()
        _alias(data, "led_red")["unexpected"] = True
        with self.assertRaisesRegex(IoAliasRegistryError, "unknown field"):
            load_io_alias_registry_from_mapping(data)

        data = fixture_mapping()
        output_state = _alias(data, "camera_or_sync_trigger")["output_state"]
        assert isinstance(output_state, dict)
        output_state["active_value"] = "maybe"
        with self.assertRaisesRegex(IoAliasRegistryError, "active_value"):
            load_io_alias_registry_from_mapping(data)


def _alias(data: dict[str, object], name: str) -> dict[str, object]:
    aliases = data["aliases"]
    assert isinstance(aliases, list)
    for alias in aliases:
        assert isinstance(alias, dict)
        if alias["name"] == name:
            return alias
    raise AssertionError(f"missing alias fixture: {name}")


if __name__ == "__main__":
    unittest.main()
