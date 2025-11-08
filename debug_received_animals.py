#!/usr/bin/env python
"""
Debug script to diagnose why received animals are not showing up for product creation.
This script checks:
1. Animals that have been received
2. Serialization of received animals
3. Filtering logic for available animals in product creation
4. User processing unit memberships
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from meat_trace.models import Animal, Product, ProcessingUnit, ProcessingUnitUser
from meat_trace.serializers import AnimalSerializer
from django.contrib.auth.models import User
from django.db.models import Q


def print_header(title):
    """Print a formatted header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def check_received_animals():
    """Check all animals that have been received"""
    print_header("RECEIVED ANIMALS STATUS")
    
    received_animals = Animal.objects.filter(
        received_by__isnull=False,
        slaughtered=True
    ).select_related('received_by', 'transferred_to', 'farmer')
    
    print(f"\nTotal received & slaughtered animals: {received_animals.count()}")
    
    if received_animals.count() == 0:
        print("❌ NO RECEIVED ANIMALS FOUND!")
        print("   This is the root cause - animals need to be received first.")
        return
    
    print("\nDetails of received animals:")
    for animal in received_animals:
        print(f"\n  Animal ID: {animal.animal_id}")
        print(f"    Database ID: {animal.id}")
        print(f"    Species: {animal.species}")
        print(f"    Slaughtered: {animal.slaughtered}")
        print(f"    Transferred to PU: {animal.transferred_to.name if animal.transferred_to else 'None'} (ID: {animal.transferred_to_id})")
        print(f"    Received by User: {animal.received_by.username if animal.received_by else 'None'} (ID: {animal.received_by_id})")
        print(f"    Received at: {animal.received_at}")
        print(f"    Used in product: {animal.processed}")
        
        # Check if used in any products
        products_using_animal = Product.objects.filter(animal=animal)
        if products_using_animal.exists():
            print(f"    ⚠️  Already used in {products_using_animal.count()} product(s):")
            for product in products_using_animal:
                print(f"       - {product.name} (Batch: {product.batch_number})")


def check_serialized_data():
    """Check how animals are serialized for the API"""
    print_header("SERIALIZED ANIMAL DATA (API RESPONSE)")
    
    animal = Animal.objects.filter(
        received_by__isnull=False,
        slaughtered=True
    ).first()
    
    if not animal:
        print("❌ No received animals to serialize")
        return
    
    serializer = AnimalSerializer(animal)
    data = serializer.data
    
    print(f"\nSample animal: {animal.animal_id}")
    print(f"\nSerialized fields relevant to product creation:")
    print(f"  id: {data.get('id')}")
    print(f"  animal_id: {data.get('animal_id')}")
    print(f"  slaughtered: {data.get('slaughtered')}")
    print(f"  received_by: {data.get('received_by')}")
    print(f"  received_by_username: {data.get('received_by_username')}")
    print(f"  received_at: {data.get('received_at')}")
    print(f"  processed: {data.get('processed')}")
    
    if data.get('received_by') is None:
        print("\n❌ ISSUE FOUND: received_by is None in serialized data!")
        print(f"   But animal.received_by_id = {animal.received_by_id}")
        print("   This indicates a serializer issue.")


def check_user_processing_units():
    """Check user memberships in processing units"""
    print_header("USER PROCESSING UNIT MEMBERSHIPS")
    
    processor_users = User.objects.filter(profile__role='processing_unit')
    
    if not processor_users.exists():
        print("❌ No processor users found!")
        return
    
    for user in processor_users:
        print(f"\n  User: {user.username} (ID: {user.id})")
        memberships = ProcessingUnitUser.objects.filter(
            user=user,
            is_active=True,
            is_suspended=False
        ).select_related('processing_unit')
        
        if memberships.exists():
            print(f"    Member of {memberships.count()} processing unit(s):")
            for membership in memberships:
                print(f"      - {membership.processing_unit.name} (PU ID: {membership.processing_unit_id})")
                print(f"        Role: {membership.role}")
                print(f"        Joined: {membership.joined_at}")
        else:
            print("    ⚠️  Not a member of any processing units!")
        
        # Check animals received by this user
        received = Animal.objects.filter(received_by=user, slaughtered=True)
        print(f"    Animals received: {received.count()}")


def check_available_for_product_creation():
    """Check which animals should be available for product creation"""
    print_header("ANIMALS AVAILABLE FOR PRODUCT CREATION")
    
    # Get all processor users
    processor_users = User.objects.filter(profile__role='processing_unit')
    
    if not processor_users.exists():
        print("❌ No processor users found!")
        return
    
    for user in processor_users:
        print(f"\n  For User: {user.username} (ID: {user.id})")
        print("  " + "-" * 76)
        
        # Get products to check which animals have been used
        all_products = Product.objects.all()
        used_animal_ids = set(all_products.values_list('animal', flat=True))
        print(f"    Total products in system: {all_products.count()}")
        print(f"    Animals already used in products: {len(used_animal_ids)}")
        
        # Filter logic from create_product_screen.dart (line 94-98)
        # animal.slaughtered && animal.receivedBy != null && 
        # animal.receivedBy == currentUserId && !usedAnimalIds.contains(animal.id)
        
        available_animals = Animal.objects.filter(
            slaughtered=True,
            received_by=user,  # This is the KEY filter - must match user ID
        ).exclude(
            id__in=used_animal_ids
        )
        
        print(f"\n    Animals matching frontend filter criteria:")
        print(f"      - slaughtered: True")
        print(f"      - received_by: {user.id} (user ID)")
        print(f"      - not in used_animal_ids")
        print(f"    Result: {available_animals.count()} animal(s)")
        
        if available_animals.count() == 0:
            print("\n    ❌ NO ANIMALS AVAILABLE FOR THIS USER!")
            
            # Debug why
            print("\n    Debugging:")
            slaughtered_count = Animal.objects.filter(slaughtered=True).count()
            received_count = Animal.objects.filter(received_by__isnull=False).count()
            received_by_user_count = Animal.objects.filter(received_by=user).count()
            
            print(f"      Total slaughtered animals: {slaughtered_count}")
            print(f"      Total received animals: {received_count}")
            print(f"      Animals received by this specific user: {received_by_user_count}")
            
            if received_by_user_count > 0:
                print(f"\n      ✓ User HAS received {received_by_user_count} animal(s)")
                slaughtered_and_received = Animal.objects.filter(
                    slaughtered=True,
                    received_by=user
                )
                print(f"      Animals both slaughtered AND received by user: {slaughtered_and_received.count()}")
                
                if slaughtered_and_received.count() == 0:
                    print("      ❌ Animals received but NOT slaughtered!")
                elif slaughtered_and_received.count() == len(used_animal_ids):
                    print("      ℹ️  All animals already used in products")
        else:
            print(f"\n    ✓ {available_animals.count()} animal(s) available:")
            for animal in available_animals:
                print(f"      - {animal.animal_id} ({animal.species})")


def check_pending_transfers():
    """Check animals that are transferred but not yet received"""
    print_header("PENDING TRANSFERS (Not Yet Received)")
    
    pending = Animal.objects.filter(
        transferred_to__isnull=False,
        received_by__isnull=True,
        slaughtered=True
    ).select_related('transferred_to', 'farmer')
    
    print(f"\nTotal pending transfers: {pending.count()}")
    
    if pending.count() > 0:
        print("\n⚠️  These animals need to be RECEIVED before product creation:")
        for animal in pending:
            print(f"\n  Animal ID: {animal.animal_id}")
            print(f"    Species: {animal.species}")
            print(f"    Transferred to: {animal.transferred_to.name} (PU ID: {animal.transferred_to_id})")
            print(f"    Transferred at: {animal.transferred_at}")
            print(f"    Status: PENDING RECEIPT")


def main():
    """Main diagnostic function"""
    print("\n" + "╔" + "═" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "  RECEIVED ANIMALS & PRODUCT CREATION DIAGNOSTIC SCRIPT".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "═" * 78 + "╝")
    
    try:
        check_received_animals()
        check_serialized_data()
        check_user_processing_units()
        check_available_for_product_creation()
        check_pending_transfers()
        
        print_header("SUMMARY & RECOMMENDATIONS")
        print("\n1. Check if animals have been RECEIVED (not just transferred)")
        print("   - Go to Processor Dashboard > Receive Animals")
        print("   - Accept pending transfers")
        print("\n2. Verify the received_by field is set correctly in the database")
        print("   - received_by should be the User ID of the processor")
        print("\n3. Ensure animals are slaughtered before transfer")
        print("   - Only slaughtered animals can be used for product creation")
        print("\n4. Check if animals are already used in products")
        print("   - Each animal can only be used once")
        print("\n5. Verify user is a member of the processing unit")
        print("   - Check ProcessingUnitUser table")
        
        print("\n" + "=" * 80)
        print("  Diagnostic complete!")
        print("=" * 80 + "\n")
        
    except Exception as e:
        print(f"\n❌ ERROR during diagnostic: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
