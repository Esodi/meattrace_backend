#!/usr/bin/env python
"""
Test script for split carcass animal receipt functionality.
Tests the receive_animals endpoint with split carcass animals.
"""
import os
import django
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from meat_trace.models import Animal, SlaughterPart, ProcessingUnit, UserProfile, User, CarcassMeasurement
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status


def create_test_data():
    """Create test data for split carcass testing"""
    print('Creating test data...')

    # Clean up any existing test data
    UserProfile.objects.filter(user__username__in=['test_farmer', 'test_processor']).delete()
    User.objects.filter(username__in=['test_farmer', 'test_processor']).delete()
    ProcessingUnit.objects.filter(name='Test Processing Unit').delete()
    Animal.objects.filter(animal_id='TEST_SPLIT_001').delete()

    # Create processing unit
    pu = ProcessingUnit.objects.create(
        name='Test Processing Unit',
        location='Test Location'
    )

    # Create farmer user
    farmer_user = User.objects.create_user(
        username='test_farmer',
        email='farmer@test.com',
        password='testpass123'
    )
    farmer_profile = UserProfile.objects.create(
        user=farmer_user,
        role='farmer'
    )

    # Create processing unit user
    pu_user = User.objects.create_user(
        username='test_processor',
        email='processor@test.com',
        password='testpass123'
    )
    pu_profile = UserProfile.objects.create(
        user=pu_user,
        role='processing_unit',
        processing_unit=pu
    )

    # Create a split carcass animal
    animal = Animal.objects.create(
        farmer=farmer_user,
        species='cow',
        age=24,  # 2 years
        live_weight=500.0,
        animal_id='TEST_SPLIT_001'
    )

    # Create carcass measurement for split carcass
    measurement = CarcassMeasurement.objects.create(
        animal=animal,
        carcass_type='split',
        left_carcass_weight=120.0,
        right_carcass_weight=118.0,
        head_weight=15.0,
        feet_weight=12.0,
        organs_weight=25.0
    )

    # Create slaughter parts
    parts_data = [
        ('left_carcass', 120.0),
        ('right_carcass', 118.0),
        ('head', 15.0),
        ('feet', 12.0),
    ]

    parts = []
    for part_type, weight in parts_data:
        part = SlaughterPart.objects.create(
            animal=animal,
            part_type=part_type,
            weight=weight,
            weight_unit='kg'
        )
        parts.append(part)

    # Transfer parts to processing unit
    for part in parts:
        part.transferred_to = pu
        part.transferred_at = timezone.now()
        part.save()

    print(f'Created split carcass animal {animal.animal_id} with {len(parts)} parts')
    print(f'Animal is_split_carcass: {animal.is_split_carcass}')
    print(f'Animal has_slaughter_parts: {animal.has_slaughter_parts}')

    return pu_user, animal, parts


def test_split_carcass_receipt():
    """Test the split carcass receipt functionality"""
    pu_user, animal, parts = create_test_data()

    # Test the receive_animals endpoint
    client = APIClient()
    client.force_authenticate(user=pu_user)

    print('\n' + '='*60)
    print('TESTING SPLIT CARCASS RECEIPT FUNCTIONALITY')
    print('='*60)

    # Test 1: Try to receive split carcass animal as whole (should fail)
    print('\n--- Test 1: Receiving split carcass as whole animal (should fail) ---')
    response = client.post('/api/v2/animals/receive_animals/', {
        'animal_ids': [animal.id]
    }, format='json')
    print(f'Status: {response.status_code}')
    if response.status_code != 200:
        print(f'✓ Expected failure - Error: {response.data}')
        assert 'split carcass animal' in str(response.data.get('error', '')).lower()
    else:
        print('✗ Unexpected success - should have failed')
        return False

    # Test 2: Receive split carcass parts individually (should succeed)
    print('\n--- Test 2: Receiving split carcass parts individually (should succeed) ---')
    part_ids = [p.id for p in parts]
    response = client.post('/api/v2/animals/receive_animals/', {
        'part_receives': [{
            'animal_id': animal.id,
            'part_ids': part_ids
        }]
    }, format='json')
    print(f'Status: {response.status_code}')
    if response.status_code == 200:
        print(f'✓ Success: {response.data}')
        # Check if animal is now received
        animal.refresh_from_db()
        print(f'Animal received_by: {animal.received_by}')
        print(f'Animal received_at: {animal.received_at}')
        assert animal.received_by == pu_user
        assert animal.received_at is not None
    else:
        print(f'✗ Failed: {response.data}')
        return False

    # Test 3: Try to receive already received parts (should fail)
    print('\n--- Test 3: Receiving already received parts (should fail) ---')
    response = client.post('/api/v2/animals/receive_animals/', {
        'part_receives': [{
            'animal_id': animal.id,
            'part_ids': [parts[0].id]  # Try to receive first part again
        }]
    }, format='json')
    print(f'Status: {response.status_code}')
    if response.status_code != 200:
        print(f'✓ Expected failure - Error: {response.data}')
        assert 'already received' in str(response.data.get('error', '')).lower()
    else:
        print('✗ Unexpected success - should have failed')
        return False

    print('\n' + '='*60)
    print('ALL TESTS PASSED! ✓')
    print('Split carcass receipt functionality working correctly.')
    print('='*60)
    return True


if __name__ == '__main__':
    try:
        success = test_split_carcass_receipt()
        if success:
            print('\n🎉 Test completed successfully!')
            sys.exit(0)
        else:
            print('\n❌ Test failed!')
            sys.exit(1)
    except Exception as e:
        print(f'\n*** Test failed with exception: {e} ***')
        import traceback
        traceback.print_exc()
        sys.exit(1)