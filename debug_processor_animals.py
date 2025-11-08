"""Debug script to check processor's animal visibility"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from meat_trace.models import Animal, ProcessingUnit, ProcessingUnitUser
from django.contrib.auth.models import User
from django.db.models import Q

# Get user ID 8 (the processor)
user = User.objects.get(id=8)
print("=" * 80)
print(f"DEBUGGING PROCESSOR ANIMAL VISIBILITY")
print("=" * 80)
print(f"User: {user.username} (ID: {user.id})")
print(f"Role: {user.profile.role}")
print(f"Primary processing unit: {user.profile.processing_unit}")
print()

# Check processing unit memberships
memberships = ProcessingUnitUser.objects.filter(user=user, is_active=True, is_suspended=False)
print(f"Active Processing Unit Memberships: {memberships.count()}")
pu_ids = list(memberships.values_list('processing_unit_id', flat=True))
print(f"Processing Unit IDs: {pu_ids}")
print()

for membership in memberships:
    print(f"  - {membership.processing_unit.name} (ID: {membership.processing_unit.id})")
    print(f"    Role: {membership.role}, Active: {membership.is_active}")
print()

# Check all animals transferred to ANY processing unit
all_transferred_animals = Animal.objects.filter(transferred_to__isnull=False)
print(f"Total animals transferred to ANY processing unit: {all_transferred_animals.count()}")
for animal in all_transferred_animals[:10]:
    print(f"  - {animal.animal_id}: transferred_to PU ID={animal.transferred_to_id}, farmer={animal.farmer.username}")
print()

# Check animals transferred to this user's processing units (exact query from views.py)
if pu_ids:
    animals_for_user = Animal.objects.filter(
        Q(transferred_to_id__in=pu_ids) |
        Q(slaughter_parts__transferred_to_id__in=pu_ids)
    ).distinct()
    
    print(f"Animals visible to user (using get_queryset logic): {animals_for_user.count()}")
    for animal in animals_for_user[:10]:
        print(f"  - {animal.animal_id}:")
        print(f"    Whole animal transferred_to: {animal.transferred_to_id}")
        print(f"    Farmer: {animal.farmer.username}")
        print(f"    Received by: {animal.received_by_id}")
        
        # Check parts
        parts = animal.slaughter_parts.all()
        if parts:
            print(f"    Parts count: {parts.count()}")
            for part in parts[:3]:
                print(f"      * {part.part_type}: transferred_to PU ID={part.transferred_to_id}")
else:
    print("User has no active processing unit memberships!")

print()
print("=" * 80)
print("CHECKING RECENT TRANSFERS")
print("=" * 80)

# Check most recent transfers by any farmer
recent_transfers = Animal.objects.filter(transferred_to__isnull=False).order_by('-transferred_at')[:5]
print(f"Most recent transfers (any farmer): {recent_transfers.count()}")
for animal in recent_transfers:
    print(f"  - {animal.animal_id}:")
    print(f"    Farmer: {animal.farmer.username} (ID: {animal.farmer.id})")
    print(f"    Transferred to PU ID: {animal.transferred_to_id}")
    print(f"    Transferred at: {animal.transferred_at}")
    print(f"    Received by: {animal.received_by_id}")
