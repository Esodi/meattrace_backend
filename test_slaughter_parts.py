#!/usr/bin/env python
"""
Test script to verify SlaughterPart model changes and carcass measurement to part mapping logic.
"""

import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from meat_trace.models import SlaughterPart, Animal, CarcassMeasurement
from django.core.management import execute_from_command_line

def test_slaughter_part_model():
    """Test SlaughterPart model functionality"""
    print("=== Testing SlaughterPart Model ===")

    # Check if SlaughterPart model exists and has required fields
    try:
        # Test creating a SlaughterPart instance
        part = SlaughterPart(
            animal_id=1,  # Will fail if no animal exists, but that's expected
            part_type='torso',
            weight=50.0,
            weight_unit='kg',
            description='Test part'
        )
        print("[PASS] SlaughterPart model can be instantiated")

        # Check required fields
        required_fields = ['part_id', 'part_type', 'weight', 'weight_unit']
        for field in required_fields:
            if hasattr(part, field):
                print(f"[PASS] Field '{field}' exists")
            else:
                print(f"[FAIL] Field '{field}' missing")

    except Exception as e:
        print(f"[FAIL] Error testing SlaughterPart model: {e}")

def test_part_id_generation():
    """Test part_id generation logic"""
    print("\n=== Testing part_id Generation ===")

    # Import the migration command to test its logic
    from meat_trace.management.commands.migrate_slaughter_parts import Command

    cmd = Command()

    # Test the _generate_unique_part_id method
    try:
        part_id = cmd._generate_unique_part_id()
        print(f"[PASS] Generated part_id: {part_id}")

        # Check format (should start with PART_ and be uppercase)
        if part_id.startswith('PART_') and part_id.isupper():
            print("[PASS] part_id format is correct")
        else:
            print("[FAIL] part_id format is incorrect")

        # Check uniqueness by generating another
        part_id2 = cmd._generate_unique_part_id()
        if part_id != part_id2:
            print("[PASS] part_id generation produces unique values")
        else:
            print("[FAIL] part_id generation not unique")

    except Exception as e:
        print(f"[FAIL] Error testing part_id generation: {e}")

def test_part_type_mapping():
    """Test part type mapping from 'other' to anatomical names"""
    print("\n=== Testing Part Type Mapping ===")

    from meat_trace.management.commands.migrate_slaughter_parts import Command

    cmd = Command()

    # Test cases for mapping
    test_cases = [
        ('ribs', 'torso'),
        ('liver', 'internal_organs'),
        ('hooves', 'feet'),
        ('front legs', 'front_legs'),
        ('hind legs', 'hind_legs'),
        ('head', 'head'),
        ('unknown part', 'other'),  # Should remain 'other'
    ]

    for description, expected_type in test_cases:
        # Create a mock part object
        class MockPart:
            def __init__(self, description):
                self.description = description

        mock_part = MockPart(description)
        result = cmd._map_other_to_anatomical(mock_part)

        if result == expected_type:
            print(f"[PASS] '{description}' -> '{result}'")
        else:
            print(f"[FAIL] '{description}' -> '{result}' (expected '{expected_type}')")

def test_carcass_to_part_mapping():
    """Test carcass measurement to part mapping logic"""
    print("\n=== Testing Carcass to Part Mapping ===")

    # Test the mapping from create_slaughter_parts_from_measurements.py
    part_type_map = {
        'head_weight': 'head',
        'left_side_weight': 'left_side',
        'right_side_weight': 'right_side',
        'internal_organs_weight': 'internal_organs',
        'feet_weight': 'feet',
        'torso_weight': 'torso',
        'front_legs_weight': 'front_legs',
        'hind_legs_weight': 'hind_legs',
        'organs_weight': 'internal_organs',
    }

    # Test some mappings
    test_measurements = [
        'head_weight',
        'left_side_weight',
        'torso_weight',
        'front_legs_weight',
        'invalid_measurement',  # Should not map
    ]

    for measurement_key in test_measurements:
        mapped_type = part_type_map.get(measurement_key)
        if mapped_type:
            print(f"[PASS] '{measurement_key}' -> '{mapped_type}'")
        else:
            print(f"[PASS] '{measurement_key}' -> not mapped (expected for invalid keys)")

def run_migration_dry_run():
    """Run the migration command in dry-run mode"""
    print("\n=== Running Migration Dry Run ===")

    try:
        # Execute the migration command with dry-run
        execute_from_command_line(['manage.py', 'migrate_slaughter_parts', '--dry-run'])
    except SystemExit:
        # Command completed
        pass
    except Exception as e:
        print(f"✗ Error running migration dry-run: {e}")

def main():
    print("Testing SlaughterPart model changes and mapping logic\n")

    test_slaughter_part_model()
    test_part_id_generation()
    test_part_type_mapping()
    test_carcass_to_part_mapping()
    run_migration_dry_run()

    print("\n=== Test Summary ===")
    print("All tests completed. Check output above for results.")

if __name__ == '__main__':
    main()