#!/usr/bin/env python
"""
Test the complete receive flow to identify where the issue occurs
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from meat_trace.models import Animal
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from django.utils import timezone


def main():
    print("\n" + "=" * 80)
    print("  TESTING RECEIVE ANIMALS FLOW")
    print("=" * 80)
    
    # Get a processor user
    processor = User.objects.filter(profile__role='processing_unit').first()
    if not processor:
        print("❌ No processor user found!")
        return
    
    print(f"\n✓ Using processor: {processor.username} (ID: {processor.id})")
    
    # Get pending animals
    pending_animals = Animal.objects.filter(
        transferred_to__isnull=False,
        received_by__isnull=True,
        slaughtered=True
    )
    
    print(f"✓ Found {pending_animals.count()} pending animals")
    
    if pending_animals.count() == 0:
        print("  No pending animals to test with")
        return
    
    # Get one animal to test
    test_animal = pending_animals.first()
    print(f"\n  Test animal: {test_animal.animal_id}")
    print(f"    transferred_to: {test_animal.transferred_to_id}")
    print(f"    received_by: {test_animal.received_by_id}")
    print(f"    received_at: {test_animal.received_at}")
    
    # Test the receive_animals API endpoint
    print("\n" + "-" * 80)
    print("  TESTING API ENDPOINT: /api/v2/animals/receive_animals/")
    print("-" * 80)
    
    client = APIClient()
    client.force_authenticate(user=processor)
    
    # Prepare request data
    data = {
        'animal_ids': [test_animal.id],
        'part_receives': [],
        'animal_rejections': [],
        'part_rejections': []
    }
    
    print(f"\n  Request data: {data}")
    
    # Make the request
    response = client.post('/api/v2/animals/receive_animals/', data, format='json')
    
    print(f"\n  Response status: {response.status_code}")
    print(f"  Response data: {response.data}")
    
    # Check database after request
    test_animal.refresh_from_db()
    
    print(f"\n  After receive_animals API call:")
    print(f"    received_by: {test_animal.received_by_id} ({'✓ SET' if test_animal.received_by_id else '❌ NOT SET'})")
    print(f"    received_at: {test_animal.received_at} ({'✓ SET' if test_animal.received_at else '❌ NOT SET'})")
    
    if test_animal.received_by_id and test_animal.received_at:
        print("\n✅ SUCCESS: Animal was properly received!")
    else:
        print("\n❌ FAILURE: Animal was NOT properly received!")
        print("   This indicates an issue with the receive_animals endpoint")
    
    # Test fetching animals after receive
    print("\n" + "-" * 80)
    print("  TESTING API ENDPOINT: /api/v2/animals/ (GET)")
    print("-" * 80)
    
    response = client.get('/api/v2/animals/')
    animals = response.data if isinstance(response.data, list) else response.data.get('results', [])
    
    print(f"\n  Total animals returned: {len(animals)}")
    
    # Find our test animal in results
    our_animal = None
    for animal_data in animals:
        if animal_data['id'] == test_animal.id:
            our_animal = animal_data
            break
    
    if our_animal:
        print(f"\n  ✓ Found test animal in API response:")
        print(f"    id: {our_animal.get('id')}")
        print(f"    animal_id: {our_animal.get('animal_id')}")
        print(f"    received_by: {our_animal.get('received_by')}")
        print(f"    received_at: {our_animal.get('received_at')}")
        print(f"    slaughtered: {our_animal.get('slaughtered')}")
    else:
        print(f"\n  ❌ Test animal NOT found in API response!")
        print("     This indicates a filtering issue in get_queryset()")
    
    print("\n" + "=" * 80)
    print("  Test complete!")
    print("=" * 80 + "\n")


if __name__ == '__main__':
    main()
