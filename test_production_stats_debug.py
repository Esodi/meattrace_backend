#!/usr/bin/env python
"""
Test script with debugging to see what's happening in production_stats_view
"""
import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from django.contrib.auth.models import User
from meat_trace.models import UserProfile, ProcessingUnit, ProcessingUnitUser
from rest_framework.test import APIClient
import json

def test_with_debugging():
    """Test with debugging enabled"""
    
    print("\n" + "="*60)
    print("  PRODUCTION STATS DEBUG TEST")
    print("="*60)
    
    # Get user and check profile
    user = User.objects.get(username='bbb')
    profile = user.profile
    
    print(f"\nUser: {user.username}")
    print(f"Profile Role: {profile.role}")
    print(f"Profile Type: {type(profile.role)}")
    print(f"Is 'processing_unit'? {profile.role == 'processing_unit'}")
    print(f"Is 'Processor'? {profile.role == 'Processor'}")
    
    # Check ProcessingUnitUser
    pu_users = ProcessingUnitUser.objects.filter(
        user=user,
        is_active=True,
        is_suspended=False
    )
    print(f"\nProcessingUnitUser count: {pu_users.count()}")
    for pu_user in pu_users:
        print(f"  - PU: {pu_user.processing_unit.name} (ID: {pu_user.processing_unit.id})")
    
    # Login and test API
    client = APIClient()
    login_data = {'username': 'bbb', 'password': 'bbbbbb'}
    response = client.post('/api/v2/token/', login_data, format='json')
    
    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data.get('access')
        print(f"\n✓ Login successful")
        
        # Test production stats
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = client.get('/api/v2/production-stats/')
        
        print(f"\nProduction Stats Response:")
        print(f"Status: {response.status_code}")
        print(f"Data: {json.dumps(response.json(), indent=2)}")
    else:
        print(f"\n✗ Login failed: {response.status_code}")

if __name__ == '__main__':
    try:
        test_with_debugging()
    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
