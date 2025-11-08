#!/usr/bin/env python
"""
Script to simulate the API call that Flutter app makes to /api/animals/
and verify rejected animals are not included in the response.

Usage: python test_api_animals_endpoint.py
"""

import os
import sys
import django
import json

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from django.contrib.auth.models import User
from django.test import RequestFactory
from meat_trace.views import AnimalViewSet
from rest_framework.test import force_authenticate

def main():
    print("=" * 80)
    print("API ENDPOINT TEST - /api/animals/")
    print("Testing what Flutter app receives when calling the animals endpoint")
    print("=" * 80)
    print()
    
    # Get user 'bbb'
    username = 'bbb'
    try:
        user = User.objects.get(username=username)
        print(f"✅ Authenticated as: {username} (ID: {user.id})")
        print()
    except User.DoesNotExist:
        print(f"❌ User '{username}' not found!")
        return
    
    # Simulate the get_queryset() logic from AnimalViewSet
    from meat_trace.models import Animal, ProcessingUnitUser
    from django.db.models import Q
    
    # Get user's processing units
    user_processing_units = ProcessingUnitUser.objects.filter(
        user=user,
        is_active=True,
        is_suspended=False
    ).values_list('processing_unit_id', flat=True)
    
    # Simulate the queryset that the API returns
    queryset = Animal.objects.filter(
        Q(transferred_to_id__in=user_processing_units) |
        Q(slaughter_parts__transferred_to_id__in=user_processing_units)
    ).exclude(
        rejection_status='rejected'
    ).distinct().select_related('farmer', 'transferred_to', 'received_by')
    
    print("-" * 80)
    print("API RESPONSE ANALYSIS")
    print("-" * 80)
    print()
    
    print(f"📊 Total animals in API response: {queryset.count()}")
    print()
    
    # Check for rejected animals in the response
    rejected_count = queryset.filter(rejection_status='rejected').count()
    
    if rejected_count > 0:
        print(f"❌ BUG FOUND: {rejected_count} REJECTED animals in API response!")
        print()
        print("Rejected animals that should NOT be in response:")
        for animal in queryset.filter(rejection_status='rejected'):
            print(f"  - {animal.animal_id} ({animal.species})")
            print(f"    Rejected by: {animal.rejected_by.username if animal.rejected_by else 'N/A'}")
            print(f"    Rejection reason: {animal.rejection_reason_specific or 'N/A'}")
        print()
    else:
        print("✅ CORRECT: No rejected animals in API response")
        print()
    
    # List all animals in the response
    print("-" * 80)
    print("ANIMALS IN API RESPONSE")
    print("-" * 80)
    print()
    
    print(f"{'Animal ID':<20} {'Species':<10} {'Received':<10} {'Rejected':<10} {'Should Show':<15}")
    print("-" * 80)
    
    for animal in queryset:
        animal_id = animal.animal_id
        species = animal.species[:10]
        received = "Yes" if animal.received_by else "No"
        rejected = "YES" if animal.rejection_status == 'rejected' else "No"
        
        # Determine if it should show on receive screen
        if animal.rejection_status == 'rejected':
            should_show = "🚫 NO (rejected)"
        elif animal.received_by:
            should_show = "No (received)"
        else:
            should_show = "✅ YES"
        
        print(f"{animal_id:<20} {species:<10} {received:<10} {rejected:<10} {should_show:<15}")
    
    print()
    print("-" * 80)
    print("SUMMARY")
    print("-" * 80)
    print()
    
    # Count animals by status
    pending = queryset.filter(received_by__isnull=True, rejection_status__isnull=True).count()
    received = queryset.filter(received_by__isnull=False).count()
    rejected = queryset.filter(rejection_status='rejected').count()
    
    print(f"✅ Pending (should show on receive screen): {pending}")
    print(f"📥 Already received (hidden): {received}")
    print(f"🚫 Rejected (should be filtered out): {rejected}")
    print()
    
    if rejected > 0:
        print("❌ ERROR: Rejected animals are in the API response!")
        print("   This means the backend filter is NOT working correctly.")
        print()
    else:
        print("✅ SUCCESS: Backend is correctly filtering out rejected animals!")
        print()
    
    print("=" * 80)
    print("FLUTTER APP SHOULD RECEIVE:")
    print("=" * 80)
    print()
    print(f"📱 {pending} animals/parts to show on receive screen")
    print(f"   (Pending items that are not received and not rejected)")
    print()
    
    # Check specific rejected animal
    print("=" * 80)
    print("CHECKING SPECIFIC REJECTED ANIMAL: ANIMAL_27DB9898F087")
    print("=" * 80)
    print()
    
    from meat_trace.models import Animal
    try:
        rejected_animal = Animal.objects.get(animal_id='ANIMAL_27DB9898F087')
        print(f"Animal ID: {rejected_animal.animal_id}")
        print(f"Species: {rejected_animal.species}")
        print(f"Transferred To: {rejected_animal.transferred_to_id}")
        print(f"Received By: {rejected_animal.received_by_id or 'Not received'}")
        print(f"Rejection Status: {rejected_animal.rejection_status or 'Not rejected'}")
        print(f"Rejected By: {rejected_animal.rejected_by.username if rejected_animal.rejected_by else 'N/A'}")
        print(f"Rejection Reason: {rejected_animal.rejection_reason_specific or 'N/A'}")
        print()
        
        # Check if it's in the API queryset
        is_in_queryset = queryset.filter(id=rejected_animal.id).exists()
        print(f"Is in API queryset: {'❌ YES (BUG!)' if is_in_queryset else '✅ NO (correct)'}")
        print()
        
    except Animal.DoesNotExist:
        print("Animal not found in database")
        print()
    
    print("=" * 80)


if __name__ == '__main__':
    main()
