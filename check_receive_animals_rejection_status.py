#!/usr/bin/env python
"""
Script to check animals listed on receive animals screen and their rejection status.
This helps verify if rejected animals are properly filtered out.

Usage: python check_receive_animals_rejection_status.py
"""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from django.contrib.auth.models import User
from meat_trace.models import Animal, SlaughterPart, ProcessingUnitUser

def main():
    print("=" * 80)
    print("RECEIVE ANIMALS SCREEN - REJECTION STATUS CHECK")
    print("=" * 80)
    print()
    
    # Login as user 'bbb'
    username = 'bbb'
    try:
        user = User.objects.get(username=username)
        print(f"✅ Found user: {username} (ID: {user.id})")
        print(f"   Email: {user.email}")
        print(f"   Role: {user.profile.role if hasattr(user, 'profile') else 'N/A'}")
        print()
    except User.DoesNotExist:
        print(f"❌ User '{username}' not found!")
        return
    
    # Get user's processing units
    user_processing_units = ProcessingUnitUser.objects.filter(
        user=user,
        is_active=True,
        is_suspended=False
    ).values_list('processing_unit_id', flat=True)
    
    print(f"🏭 Processing Units for user '{username}':")
    if user_processing_units:
        for pu_id in user_processing_units:
            print(f"   - Processing Unit ID: {pu_id}")
        print()
    else:
        print("   ⚠️  No processing units found for this user")
        print()
    
    print("-" * 80)
    print("WHOLE ANIMALS - Transferred to Processing Units")
    print("-" * 80)
    print()
    
    # Check whole animals transferred to user's processing units
    whole_animals = Animal.objects.filter(
        transferred_to_id__in=user_processing_units
    ).order_by('-transferred_at')
    
    print(f"📊 Total whole animals transferred to processing units: {whole_animals.count()}")
    print()
    
    if whole_animals.exists():
        print(f"{'Animal ID':<15} {'Species':<10} {'Received':<12} {'Rejected':<12} {'Status':<20}")
        print("-" * 80)
        
        for animal in whole_animals:
            animal_id = animal.animal_id
            species = animal.species[:10]
            received = "✅ Yes" if animal.received_by else "⏳ No"
            rejected = "❌ Yes" if animal.rejection_status == 'rejected' else "✅ No"
            
            # Determine what should happen on receive screen
            if animal.rejection_status == 'rejected':
                status = "🚫 SHOULD NOT SHOW"
            elif animal.received_by:
                status = "✅ RECEIVED - Hidden"
            else:
                status = "📋 SHOULD SHOW"
            
            print(f"{animal_id:<15} {species:<10} {received:<12} {rejected:<12} {status:<20}")
            
            # Show additional details for rejected animals
            if animal.rejection_status == 'rejected':
                print(f"   └─ Rejected by: {animal.rejected_by.username if animal.rejected_by else 'N/A'}")
                print(f"   └─ Rejection reason: {animal.rejection_reason_specific or 'N/A'}")
                print(f"   └─ Rejected at: {animal.rejected_at or 'N/A'}")
        print()
    
    print("-" * 80)
    print("SLAUGHTER PARTS - Transferred to Processing Units")
    print("-" * 80)
    print()
    
    # Check slaughter parts transferred to user's processing units
    parts = SlaughterPart.objects.filter(
        transferred_to_id__in=user_processing_units
    ).select_related('animal').order_by('-transferred_at')
    
    print(f"📊 Total slaughter parts transferred to processing units: {parts.count()}")
    print()
    
    if parts.exists():
        print(f"{'Part ID':<15} {'Animal ID':<15} {'Part Type':<15} {'Received':<12} {'Rejected':<12} {'Status':<20}")
        print("-" * 80)
        
        for part in parts:
            part_id = part.part_id or f"ID-{part.id}"
            animal_id = part.animal.animal_id
            part_type = part.part_type[:15]
            received = "✅ Yes" if part.received_by else "⏳ No"
            rejected = "❌ Yes" if part.rejection_status == 'rejected' else "✅ No"
            
            # Determine what should happen on receive screen
            if part.rejection_status == 'rejected':
                status = "🚫 SHOULD NOT SHOW"
            elif part.received_by:
                status = "✅ RECEIVED - Hidden"
            else:
                status = "📋 SHOULD SHOW"
            
            print(f"{part_id:<15} {animal_id:<15} {part_type:<15} {received:<12} {rejected:<12} {status:<20}")
            
            # Show additional details for rejected parts
            if part.rejection_status == 'rejected':
                print(f"   └─ Rejected by: {part.rejected_by.username if part.rejected_by else 'N/A'}")
                print(f"   └─ Rejection reason: {part.rejection_reason_specific or 'N/A'}")
                print(f"   └─ Rejected at: {part.rejected_at or 'N/A'}")
        print()
    
    print("=" * 80)
    print("SUMMARY - What should appear on Receive Animals Screen")
    print("=" * 80)
    print()
    
    # Animals that should show (not received and not rejected)
    pending_whole_animals = whole_animals.filter(
        received_by__isnull=True,
        rejection_status__isnull=True
    ).count()
    
    pending_parts = parts.filter(
        received_by__isnull=True,
        rejection_status__isnull=True
    ).count()
    
    # Animals that are rejected (should NOT show)
    rejected_whole_animals = whole_animals.filter(
        rejection_status='rejected'
    ).count()
    
    rejected_parts = parts.filter(
        rejection_status='rejected'
    ).count()
    
    # Animals that are received (should NOT show)
    received_whole_animals = whole_animals.filter(
        received_by__isnull=False,
        rejection_status__isnull=True
    ).count()
    
    received_parts = parts.filter(
        received_by__isnull=False,
        rejection_status__isnull=True
    ).count()
    
    print("✅ SHOULD APPEAR ON RECEIVE SCREEN (Pending - Not Received, Not Rejected):")
    print(f"   - Whole Animals: {pending_whole_animals}")
    print(f"   - Slaughter Parts: {pending_parts}")
    print(f"   - TOTAL: {pending_whole_animals + pending_parts}")
    print()
    
    print("🚫 SHOULD NOT APPEAR (Rejected):")
    print(f"   - Whole Animals: {rejected_whole_animals}")
    print(f"   - Slaughter Parts: {rejected_parts}")
    print(f"   - TOTAL: {rejected_whole_animals + rejected_parts}")
    print()
    
    print("✅ SHOULD NOT APPEAR (Already Received):")
    print(f"   - Whole Animals: {received_whole_animals}")
    print(f"   - Slaughter Parts: {received_parts}")
    print(f"   - TOTAL: {received_whole_animals + received_parts}")
    print()
    
    # Check if backend queryset is filtering correctly
    print("=" * 80)
    print("BACKEND QUERYSET CHECK")
    print("=" * 80)
    print()
    
    # Simulate what the AnimalViewSet.get_queryset() returns
    from django.db.models import Q
    
    backend_queryset = Animal.objects.filter(
        Q(transferred_to_id__in=user_processing_units) |
        Q(slaughter_parts__transferred_to_id__in=user_processing_units)
    ).exclude(
        rejection_status='rejected'
    ).distinct()
    
    print(f"📊 Animals returned by AnimalViewSet queryset: {backend_queryset.count()}")
    print(f"   (Should exclude rejected animals)")
    print()
    
    # Check if any rejected animals are in the queryset (bug if > 0)
    rejected_in_queryset = backend_queryset.filter(rejection_status='rejected').count()
    if rejected_in_queryset > 0:
        print(f"❌ BUG FOUND: {rejected_in_queryset} rejected animals in queryset!")
    else:
        print(f"✅ CORRECT: No rejected animals in queryset")
    print()
    
    # Simulate what the SlaughterPartViewSet.get_queryset() returns
    backend_parts_queryset = SlaughterPart.objects.filter(
        Q(transferred_to_id__in=user_processing_units) |
        Q(received_by=user)
    ).exclude(
        rejection_status='rejected'
    )
    
    print(f"📊 Parts returned by SlaughterPartViewSet queryset: {backend_parts_queryset.count()}")
    print(f"   (Should exclude rejected parts)")
    print()
    
    # Check if any rejected parts are in the queryset (bug if > 0)
    rejected_parts_in_queryset = backend_parts_queryset.filter(rejection_status='rejected').count()
    if rejected_parts_in_queryset > 0:
        print(f"❌ BUG FOUND: {rejected_parts_in_queryset} rejected parts in queryset!")
    else:
        print(f"✅ CORRECT: No rejected parts in queryset")
    print()
    
    print("=" * 80)
    print("✅ CHECK COMPLETE")
    print("=" * 80)


if __name__ == '__main__':
    main()
