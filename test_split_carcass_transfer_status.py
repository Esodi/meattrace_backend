"""
Test script to verify that split carcass animals are properly marked as transferred
when all their parts are transferred, and that they appear in the farmer dashboard.
"""

import os
import django
import sys

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from django.contrib.auth.models import User
from meat_trace.models import Animal, SlaughterPart, ProcessingUnit, CarcassMeasurement, UserProfile
from django.utils import timezone
from decimal import Decimal


def cleanup_test_data():
    """Clean up any existing test data"""
    print("\n" + "="*80)
    print("CLEANING UP TEST DATA")
    print("="*80)
    
    # Delete test animals and parts
    Animal.objects.filter(animal_id__startswith='TEST_SPLIT_').delete()
    ProcessingUnit.objects.filter(name='Test Processing Unit Transfer').delete()
    User.objects.filter(username__in=['test_farmer_transfer', 'test_processor_transfer']).delete()
    
    print("✓ Test data cleaned up")


def create_test_data():
    """Create test data for split carcass transfer testing"""
    print("\n" + "="*80)
    print("CREATING TEST DATA")
    print("="*80)
    
    # Create farmer user
    farmer = User.objects.create_user(
        username='test_farmer_transfer',
        password='testpass123',
        email='farmer@test.com'
    )
    UserProfile.objects.create(user=farmer, role='Farmer')
    print(f"✓ Created farmer: {farmer.username}")
    
    # Create processor user and processing unit
    processor = User.objects.create_user(
        username='test_processor_transfer',
        password='testpass123',
        email='processor@test.com'
    )
    processor_profile = UserProfile.objects.create(user=processor, role='Processor')
    
    processing_unit = ProcessingUnit.objects.create(
        name='Test Processing Unit Transfer',
        location='Test Location',
        contact_email='pu@test.com'
    )
    processor_profile.processing_unit = processing_unit
    processor_profile.save()
    print(f"✓ Created processing unit: {processing_unit.name}")
    
    # Create a split carcass animal
    animal = Animal.objects.create(
        farmer=farmer,
        species='cow',
        age=Decimal('24.0'),
        live_weight=Decimal('450.0'),
        slaughtered=True,
        slaughtered_at=timezone.now(),
        animal_id='TEST_SPLIT_CARCASS_001'
    )
    
    # Create carcass measurement
    measurement = CarcassMeasurement.objects.create(
        animal=animal,
        carcass_type='split',
        left_carcass_weight=Decimal('100.0'),
        right_carcass_weight=Decimal('100.0'),
        feet_weight=Decimal('10.0'),
        organs_weight=Decimal('15.0')
    )
    print(f"✓ Created split carcass animal: {animal.animal_id}")
    
    # Create slaughter parts
    parts = [
        SlaughterPart.objects.create(
            animal=animal,
            part_type='left_carcass',
            weight=Decimal('100.0')
        ),
        SlaughterPart.objects.create(
            animal=animal,
            part_type='right_carcass',
            weight=Decimal('100.0')
        ),
        SlaughterPart.objects.create(
            animal=animal,
            part_type='feet',
            weight=Decimal('10.0')
        ),
        SlaughterPart.objects.create(
            animal=animal,
            part_type='internal_organs',
            weight=Decimal('15.0')
        ),
    ]
    print(f"✓ Created {len(parts)} slaughter parts")
    
    return farmer, processing_unit, animal, parts


def test_partial_transfer(farmer, processing_unit, animal, parts):
    """Test transferring only some parts - animal should NOT be marked as transferred"""
    print("\n" + "="*80)
    print("TEST 1: PARTIAL TRANSFER (Only 2 out of 4 parts)")
    print("="*80)
    
    # Transfer only the first 2 parts
    for part in parts[:2]:
        part.transferred_to = processing_unit
        part.transferred_at = timezone.now()
        part.save()
    
    # Refresh animal from database
    animal.refresh_from_db()
    
    print(f"Parts transferred: 2 out of {len(parts)}")
    print(f"Animal.transferred_to: {animal.transferred_to}")
    print(f"Animal.lifecycle_status: {animal.lifecycle_status}")
    
    # Check results
    assert animal.transferred_to is None, "❌ Animal should NOT be marked as transferred (only partial transfer)"
    assert animal.lifecycle_status == 'SEMI-TRANSFERRED', f"❌ Lifecycle status should be SEMI-TRANSFERRED, got {animal.lifecycle_status}"
    
    print("✓ PASSED: Animal is not marked as transferred with partial parts")
    
    # Reset for next test
    for part in parts:
        part.transferred_to = None
        part.transferred_at = None
        part.save()
    animal.transferred_to = None
    animal.transferred_at = None
    animal.save()


def test_complete_transfer(farmer, processing_unit, animal, parts):
    """Test transferring all parts - animal SHOULD be marked as transferred"""
    print("\n" + "="*80)
    print("TEST 2: COMPLETE TRANSFER (All 4 parts)")
    print("="*80)
    
    # Simulate the transfer endpoint logic
    transferred_parts = []
    animals_with_transferred_parts = set()
    
    for part in parts:
        part.transferred_to = processing_unit
        part.transferred_at = timezone.now()
        part.save()
        transferred_parts.append(part)
        animals_with_transferred_parts.add(part.animal)
    
    # Check if all parts of any animal are now transferred
    # If so, mark the parent animal as transferred
    transferred_animals = []
    for animal_obj in animals_with_transferred_parts:
        all_parts = animal_obj.slaughter_parts.all()
        if all_parts.exists():
            transferred_parts_count = sum(1 for p in all_parts if p.transferred_to is not None)
            
            # If all parts are transferred, mark the animal as transferred
            if transferred_parts_count == len(all_parts):
                animal_obj.transferred_to = processing_unit
                animal_obj.transferred_at = timezone.now()
                animal_obj.save()
                transferred_animals.append(animal_obj)
                print(f"✓ All {len(all_parts)} parts transferred - marking animal as transferred")
    
    # Refresh animal from database
    animal.refresh_from_db()
    
    print(f"\nParts transferred: {len(transferred_parts)} out of {len(parts)}")
    print(f"Animal.transferred_to: {animal.transferred_to}")
    print(f"Animal.transferred_at: {animal.transferred_at}")
    print(f"Animal.lifecycle_status: {animal.lifecycle_status}")
    
    # Check results
    assert animal.transferred_to == processing_unit, f"❌ Animal should be marked as transferred to {processing_unit}, got {animal.transferred_to}"
    assert animal.transferred_at is not None, "❌ Animal.transferred_at should be set"
    assert animal.lifecycle_status == 'TRANSFERRED', f"❌ Lifecycle status should be TRANSFERRED, got {animal.lifecycle_status}"
    
    print("\n✓ PASSED: Animal is properly marked as transferred when all parts are transferred")


def test_farmer_dashboard_visibility(farmer, animal):
    """Test that transferred split carcass animals appear in farmer's transferred animals list"""
    print("\n" + "="*80)
    print("TEST 3: FARMER DASHBOARD VISIBILITY")
    print("="*80)
    
    # Query for transferred animals (simulating the endpoint logic)
    transferred_animals = Animal.objects.filter(
        farmer=farmer,
        transferred_to__isnull=False
    ).order_by('-transferred_at')
    
    print(f"Total animals owned by farmer: {Animal.objects.filter(farmer=farmer).count()}")
    print(f"Transferred animals found: {transferred_animals.count()}")
    
    # Check if our test animal is in the results
    animal_ids = [a.animal_id for a in transferred_animals]
    print(f"Transferred animal IDs: {animal_ids}")
    
    assert animal.animal_id in animal_ids, f"❌ Animal {animal.animal_id} should appear in transferred animals list"
    
    # Check lifecycle status via property
    for a in transferred_animals:
        print(f"  - {a.animal_id}: lifecycle_status={a.lifecycle_status}, is_split_carcass={a.is_split_carcass}")
    
    print("\n✓ PASSED: Split carcass animal appears in farmer's transferred animals list")


def run_tests():
    """Run all tests"""
    print("\n" + "="*80)
    print("SPLIT CARCASS TRANSFER STATUS TEST SUITE")
    print("="*80)
    
    try:
        # Setup
        cleanup_test_data()
        farmer, processing_unit, animal, parts = create_test_data()
        
        # Run tests
        test_partial_transfer(farmer, processing_unit, animal, parts)
        test_complete_transfer(farmer, processing_unit, animal, parts)
        test_farmer_dashboard_visibility(farmer, animal)
        
        # Cleanup
        print("\n" + "="*80)
        print("ALL TESTS PASSED! ✓")
        print("="*80)
        cleanup_test_data()
        
        return True
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
