#!/usr/bin/env python
"""
Debug Production Stats Issue
Checks why production stats are empty
"""
import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from django.contrib.auth.models import User
from meat_trace.models import UserProfile, ProcessingUnit, ProcessingUnitUser, Animal, Product
from meat_trace.models import SlaughterPart

def debug_production_stats():
    """Debug why production stats are empty"""
    
    print("\n" + "="*60)
    print("  DEBUGGING PRODUCTION STATS ISSUE")
    print("="*60)
    
    # 1. Get the user
    try:
        user = User.objects.get(username='bbb')
        profile = user.profile
        pu = profile.processing_unit
        
        print(f"\n✓ User found: {user.username} (ID: {user.id})")
        print(f"✓ Profile role: {profile.role}")
        print(f"✓ Processing Unit from profile: {pu.name if pu else 'None'} (ID: {pu.id if pu else 'N/A'})")
        
    except User.DoesNotExist:
        print("\n✗ ERROR: User 'bbb' not found!")
        return
    
    # 2. Check ProcessingUnitUser records
    print("\n" + "="*60)
    print("  CHECKING ProcessingUnitUser RECORDS")
    print("="*60)
    
    pu_users = ProcessingUnitUser.objects.filter(user=user)
    print(f"\nTotal ProcessingUnitUser records for user '{user.username}': {pu_users.count()}")
    
    for pu_user in pu_users:
        print(f"\n  Processing Unit: {pu_user.processing_unit.name} (ID: {pu_user.processing_unit.id})")
        print(f"  Role: {pu_user.role}")
        print(f"  Is Active: {pu_user.is_active}")
        print(f"  Is Suspended: {pu_user.is_suspended}")
    
    # 3. Check active and non-suspended records
    active_pu_users = ProcessingUnitUser.objects.filter(
        user=user,
        is_active=True,
        is_suspended=False
    )
    
    print(f"\nActive & Non-Suspended ProcessingUnitUser records: {active_pu_users.count()}")
    
    user_processing_units = active_pu_users.values_list('processing_unit_id', flat=True)
    print(f"Processing Unit IDs from ProcessingUnitUser: {list(user_processing_units)}")
    
    # 4. Compare with profile processing unit
    print("\n" + "="*60)
    print("  COMPARISON")
    print("="*60)
    
    if pu:
        print(f"\nProcessing Unit from UserProfile: {pu.id}")
        print(f"Processing Unit IDs from ProcessingUnitUser: {list(user_processing_units)}")
        
        if pu.id in user_processing_units:
            print("\n✓ Match found! UserProfile PU is in ProcessingUnitUser records")
        else:
            print("\n✗ NO MATCH! UserProfile PU is NOT in ProcessingUnitUser records")
            print("   This is why production stats are empty!")
    
    # 5. Show what the stats SHOULD be (using profile.processing_unit)
    if pu:
        print("\n" + "="*60)
        print("  EXPECTED STATS (using UserProfile.processing_unit)")
        print("="*60)
        
        # Count by received_by field (this is what the current code does)
        received_by_user = Animal.objects.filter(received_by=user).count()
        received_parts_by_user = SlaughterPart.objects.filter(received_by=user).count()
        
        print(f"\nAnimals received_by user: {received_by_user}")
        print(f"Parts received_by user: {received_parts_by_user}")
        print(f"Total received by user: {received_by_user + received_parts_by_user}")
        
        # Count by transferred_to (processing unit based)
        received_animals_pu = Animal.objects.filter(
            transferred_to=pu,
            received_at__isnull=False
        ).count()
        
        received_parts_pu = SlaughterPart.objects.filter(
            transferred_to=pu,
            received_at__isnull=False
        ).count()
        
        print(f"\nAnimals received by PU '{pu.name}': {received_animals_pu}")
        print(f"Parts received by PU '{pu.name}': {received_parts_pu}")
        print(f"Total received by PU: {received_animals_pu + received_parts_pu}")
        
        # Pending
        pending_animals = Animal.objects.filter(
            transferred_to=pu,
            received_by__isnull=True,
            rejection_status__isnull=True
        ).count()
        
        pending_parts = SlaughterPart.objects.filter(
            transferred_to=pu,
            received_by__isnull=True,
            rejection_status__isnull=True
        ).count()
        
        print(f"\nPending animals: {pending_animals}")
        print(f"Pending parts: {pending_parts}")
        print(f"Total pending: {pending_animals + pending_parts}")
        
        # Products
        total_products = Product.objects.filter(processing_unit=pu).count()
        in_stock = Product.objects.filter(
            processing_unit=pu,
            transferred_to__isnull=True
        ).count()
        
        print(f"\nTotal products: {total_products}")
        print(f"In stock: {in_stock}")
    
    # 6. Suggested fix
    print("\n" + "="*60)
    print("  SUGGESTED FIX")
    print("="*60)
    
    if pu and pu.id not in user_processing_units:
        print("\nThe issue is that the code uses ProcessingUnitUser table,")
        print("but the user's processing unit is set in UserProfile.")
        print("\nOptions to fix:")
        print("1. Create a ProcessingUnitUser record for this user")
        print("2. Modify the view to also check UserProfile.processing_unit")
        print("\nWould you like to create a ProcessingUnitUser record? (y/n)")
        
        # Automatically create the record
        print("\nCreating ProcessingUnitUser record...")
        pu_user, created = ProcessingUnitUser.objects.get_or_create(
            user=user,
            processing_unit=pu,
            defaults={
                'role': 'owner',
                'is_active': True,
                'is_suspended': False
            }
        )
        
        if created:
            print(f"✓ Created ProcessingUnitUser record for {user.username}")
        else:
            print(f"✓ ProcessingUnitUser record already exists")
            print(f"  Is Active: {pu_user.is_active}")
            print(f"  Is Suspended: {pu_user.is_suspended}")
            
            # Update if needed
            if not pu_user.is_active or pu_user.is_suspended:
                pu_user.is_active = True
                pu_user.is_suspended = False
                pu_user.save()
                print(f"✓ Updated ProcessingUnitUser record to active and not suspended")

if __name__ == '__main__':
    try:
        debug_production_stats()
    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
