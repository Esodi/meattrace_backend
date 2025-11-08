#!/usr/bin/env python
"""
Debug script for testing the receive_animals endpoint
"""
import os
import django
import requests
import json

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from meat_trace.models import UserProfile, ProcessingUnit, Animal, SlaughterPart
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from django.test import RequestFactory

def check_database_state():
    """Check current database state"""
    print('=== CHECKING DATABASE STATE ===')

    # Check users
    users = User.objects.all()
    print(f'Total users: {users.count()}')
    for user in users:
        print(f'  User: {user.username}, ID: {user.id}')
        try:
            profile = user.profile
            print(f'    Profile role: {profile.role}')
            if hasattr(profile, 'processing_unit') and profile.processing_unit:
                print(f'    Processing unit: {profile.processing_unit.name} (ID: {profile.processing_unit.id})')
        except:
            print('    No profile')

    # Check processing units
    pus = ProcessingUnit.objects.all()
    print(f'\nTotal processing units: {pus.count()}')
    for pu in pus:
        print(f'  PU: {pu.name}, ID: {pu.id}')

    # Check animals
    animals = Animal.objects.all()
    print(f'\nTotal animals: {animals.count()}')
    for animal in animals[:5]:  # Show first 5
        print(f'  Animal ID: {animal.animal_id}, transferred_to: {animal.transferred_to}, received_by: {animal.received_by}')

    # Check slaughter parts
    parts = SlaughterPart.objects.all()
    print(f'\nTotal slaughter parts: {parts.count()}')
    for part in parts[:10]:  # Show first 10
        print(f'  Part ID: {part.id}, type: {part.part_type}, animal: {part.animal.animal_id}, transferred_to: {part.transferred_to}, received_by: {part.received_by}')

def test_receive_animals():
    """Test the receive_animals endpoint"""
    print('\n=== TESTING RECEIVE_ANIMALS ENDPOINT ===')

    # Get a processing unit user
    try:
        pu_user = User.objects.filter(profile__role='processing_unit').first()
        if not pu_user:
            print('No processing unit user found. Creating test user...')
            # Create test user
            user = User.objects.create_user(username='test_processor', password='testpass123')
            pu = ProcessingUnit.objects.first()
            if not pu:
                pu = ProcessingUnit.objects.create(name='Test Processing Unit', location='Test Location')
            profile = UserProfile.objects.create(user=user, role='processing_unit', processing_unit=pu)
            pu_user = user
            print(f'Created test user: {pu_user.username}')

        print(f'Using user: {pu_user.username} (ID: {pu_user.id})')

        # Create API client and authenticate
        client = APIClient()
        client.force_authenticate(user=pu_user)

        # Test data from the error log
        data = {
            'part_receives': [{'animal_id': 4, 'part_ids': [5, 7]}]
        }

        print(f'Testing with data: {json.dumps(data, indent=2)}')

        # Make the request
        response = client.post('/api/v2/animals/receive_animals/', data, format='json')

        print(f'Status Code: {response.status_code}')
        print(f'Response: {response.content.decode()}')

        if response.status_code == 400:
            print('400 Error occurred - this matches the reported issue')
        elif response.status_code == 200:
            print('Request succeeded')
        else:
            print(f'Unexpected status code: {response.status_code}')

    except Exception as e:
        print(f'Error during test: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    check_database_state()
    test_receive_animals()