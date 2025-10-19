"""
Script to create SlaughterPart records from existing CarcassMeasurement records.
This is needed for animals that were slaughtered before the automatic part creation was implemented.

Run this from the Django project root:
    python create_slaughter_parts_from_measurements.py
"""

import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from meat_trace.models import Animal, CarcassMeasurement, SlaughterPart


def create_slaughter_parts_from_measurements():
    """
    For all animals with split carcass measurements but no slaughter parts,
    create SlaughterPart records from the measurements.
    """
    print("🔍 Finding animals with carcass measurements but no slaughter parts...")
    
    # Get all animals that:
    # 1. Have been slaughtered
    # 2. Have carcass measurements with split carcass type
    # 3. Don't have any slaughter parts yet
    animals_with_measurements = Animal.objects.filter(
        slaughtered=True,
        carcass_measurement__carcass_type='split'
    ).exclude(
        slaughter_parts__isnull=False
    ).select_related('carcass_measurement')
    
    count = animals_with_measurements.count()
    print(f"📊 Found {count} animals that need slaughter parts created")
    
    if count == 0:
        print("✅ No animals need processing. All done!")
        return
    
    total_parts_created = 0
    
    for animal in animals_with_measurements:
        print(f"\n🐄 Processing animal: {animal.animal_id}")
        carcass = animal.carcass_measurement
        measurements = carcass.measurements
        
        if not measurements:
            print(f"  ⚠️  No measurements data found for {animal.animal_id}")
            continue
        
        # Map of measurement keys to part types (must match PART_CHOICES in models.py)
        part_type_map = {
            'head_weight': 'head',
            'left_side_weight': 'left_side',
            'right_side_weight': 'right_side',
            'internal_organs_weight': 'internal_organs',
            'feet_weight': 'feet',
            # Legacy/custom mappings - will use 'other' if not in PART_CHOICES
            'torso_weight': 'other',
            'front_legs_weight': 'other',
            'hind_legs_weight': 'other',
            'organs_weight': 'internal_organs',
        }
        
        parts_created = 0
        
        for measurement_key, measurement_value in measurements.items():
            # Skip metadata fields
            if measurement_key in ['carcass_type', 'notes']:
                continue
            
            # Check if it's a weight measurement (has 'value' and 'unit')
            if isinstance(measurement_value, dict) and 'value' in measurement_value:
                # Get part type name from mapping (must be valid PART_CHOICES value)
                part_type = part_type_map.get(measurement_key)
                if not part_type:
                    # If no mapping exists, use 'other' as fallback
                    part_type = 'other'
                    print(f"  ⚠️  Unmapped measurement '{measurement_key}', using 'other'")
                
                weight = measurement_value.get('value')
                unit = measurement_value.get('unit', 'kg')
                
                if weight and float(weight) > 0:
                    try:
                        slaughter_part = SlaughterPart.objects.create(
                            animal=animal,
                            part_type=part_type,
                            weight=weight,
                            weight_unit=unit,
                            description=f'Created from {measurement_key} measurement'
                        )
                        parts_created += 1
                        total_parts_created += 1
                        print(f"  ✅ Created: {part_type} ({weight} {unit})")
                    except Exception as e:
                        print(f"  ❌ Error creating part '{part_type}': {e}")
        
        if parts_created > 0:
            print(f"  🎯 Total parts created for {animal.animal_id}: {parts_created}")
        else:
            print(f"  ⚠️  No valid measurements found for {animal.animal_id}")
    
    print(f"\n" + "="*60)
    print(f"✅ COMPLETE! Created {total_parts_created} slaughter parts for {count} animals")
    print(f"="*60)


if __name__ == '__main__':
    print("="*60)
    print("Creating SlaughterPart records from CarcassMeasurement data")
    print("="*60)
    
    try:
        create_slaughter_parts_from_measurements()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
