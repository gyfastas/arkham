#!/usr/bin/env python3
"""Validate a player card's JSON data, implementation, and test files."""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SCHEMA_PATH = PROJECT_ROOT / "data" / "player_cards" / "schema.json"
BACKEND_CARDS = PROJECT_ROOT / "backend" / "cards"
BACKEND_TESTS = PROJECT_ROOT / "backend" / "tests" / "test_cards"

REQUIRED_FIELDS = ["id", "name", "name_cn", "class", "type", "cost", "level"]
VALID_CLASSES = ["guardian", "seeker", "rogue", "mystic", "survivor", "neutral"]
VALID_TYPES = ["asset", "event", "skill"]


def validate_json(filepath: Path) -> dict:
    """Validate card JSON data."""
    errors = []

    if not filepath.exists():
        return {"errors": [f"File not found: {filepath}"], "data": None}

    with open(filepath) as f:
        data = json.load(f)

    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    if data.get("class") not in VALID_CLASSES:
        errors.append(f"Invalid class: {data.get('class')}. Must be one of {VALID_CLASSES}")

    if data.get("type") not in VALID_TYPES:
        errors.append(f"Invalid type: {data.get('type')}. Must be one of {VALID_TYPES}")

    if data.get("type") == "skill" and data.get("cost") is not None:
        errors.append("Skill cards should have cost: null")

    if data.get("level") is not None:
        level = data["level"]
        if not isinstance(level, int) or level < 0 or level > 5:
            errors.append(f"Level must be 0-5, got: {level}")

    return {"errors": errors, "data": data}


def check_implementation(card_id: str, card_class: str) -> list[str]:
    """Check that a card implementation module exists."""
    errors = []
    impl_dir = BACKEND_CARDS / card_class
    if not impl_dir.exists():
        errors.append(f"Implementation directory not found: {impl_dir}")
        return errors

    # Look for a .py file with the card_id
    found = False
    for py_file in impl_dir.glob("*.py"):
        if py_file.name == "__init__.py":
            continue
        content = py_file.read_text()
        if f'card_id = "{card_id}"' in content:
            found = True
            # Check it extends CardImplementation
            if "CardImplementation" not in content:
                errors.append(f"{py_file.name}: Missing CardImplementation base class")
            if "@on_event" not in content:
                errors.append(f"{py_file.name}: No @on_event handlers found")
            break

    if not found:
        errors.append(f"No implementation found with card_id = \"{card_id}\" in {impl_dir}")

    return errors


def check_tests(card_id: str) -> list[str]:
    """Check that card tests exist."""
    errors = []
    test_files = list(BACKEND_TESTS.glob(f"*{card_id}*"))

    if not test_files:
        # Try matching by card_id content inside test files
        all_tests = list(BACKEND_TESTS.glob("test_*.py"))
        test_files = [f for f in all_tests if card_id in f.read_text()]

    if not test_files:
        # Try matching card base name (strip _lvN suffix)
        base_name = card_id.rsplit("_lv", 1)[0] if "_lv" in card_id else card_id
        test_files = list(BACKEND_TESTS.glob(f"test_{base_name}*"))
        if not test_files:
            test_files = list(BACKEND_TESTS.glob(f"test_*{base_name}*"))

    if not test_files:
        errors.append(f"No test file found for card: {card_id}")
    else:
        for tf in test_files:
            content = tf.read_text()
            if "def test_" not in content:
                errors.append(f"{tf.name}: No test functions found")

    return errors


def main():
    if len(sys.argv) < 2:
        print("Usage: validate_card.py <card_json_path>")
        print("Example: validate_card.py data/player_cards/guardian/machete_lv0.json")
        sys.exit(1)

    filepath = Path(sys.argv[1])
    if not filepath.is_absolute():
        filepath = PROJECT_ROOT / filepath

    print(f"Validating: {filepath}")
    print("=" * 60)

    # 1. Validate JSON
    print("\n[1/3] Checking JSON data...")
    result = validate_json(filepath)
    if result["errors"]:
        for e in result["errors"]:
            print(f"  ✗ {e}")
    else:
        print(f"  ✓ JSON valid ({len(result['data'])} fields)")

    data = result["data"]
    all_errors = list(result["errors"])

    if data:
        card_id = data["id"]
        card_class = data["class"]

        # 2. Check implementation
        print("\n[2/3] Checking implementation...")
        impl_errors = check_implementation(card_id, card_class)
        if impl_errors:
            for e in impl_errors:
                print(f"  ✗ {e}")
        else:
            print(f"  ✓ Implementation found for {card_id}")
        all_errors.extend(impl_errors)

        # 3. Check tests
        print("\n[3/3] Checking tests...")
        test_errors = check_tests(card_id)
        if test_errors:
            for e in test_errors:
                print(f"  ✗ {e}")
        else:
            print(f"  ✓ Tests found for {card_id}")
        all_errors.extend(test_errors)

    print("\n" + "=" * 60)
    if all_errors:
        print(f"FAILED: {len(all_errors)} error(s)")
        sys.exit(1)
    else:
        print("PASSED: Card is fully registered")
        sys.exit(0)


if __name__ == "__main__":
    main()
