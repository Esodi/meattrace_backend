"""
Migration script to update existing user roles to the new standardized format.
This fixes the role inconsistency issue where roles were stored as lowercase
but the code expects capitalized versions.
"""
import os
import django
import sys

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from meat_trace.models import UserProfile

print("=" * 80)
print("MIGRATING USER ROLES TO STANDARDIZED FORMAT")
print("=" * 80)
print()

# Define the role mapping
role_mapping = {
    'farmer': 'Farmer',
    'processing_unit': 'Processor',
    'processor': 'Processor',
    'shop': 'ShopOwner',
    'shopowner': 'ShopOwner',
    'admin': 'Admin',
}

# Get all user profiles
all_profiles = UserProfile.objects.all()
print(f"Total user profiles found: {all_profiles.count()}")
print()

updated_count = 0
unchanged_count = 0

print("Updating roles:")
print("-" * 80)

for profile in all_profiles:
    old_role = profile.role
    new_role = role_mapping.get(old_role.lower(), old_role)
    
    if old_role != new_role:
        profile.role = new_role
        profile.save()
        print(f"  ✅ {profile.user.username}: '{old_role}' → '{new_role}'")
        updated_count += 1
    else:
        print(f"  ⏭️  {profile.user.username}: '{old_role}' (already correct)")
        unchanged_count += 1

print()
print("=" * 80)
print("MIGRATION COMPLETE")
print("=" * 80)
print(f"  Updated: {updated_count} users")
print(f"  Unchanged: {unchanged_count} users")
print(f"  Total: {all_profiles.count()} users")
print()

# Verify the changes
print("Current role distribution:")
print("-" * 80)
from django.db.models import Count
role_counts = UserProfile.objects.values('role').annotate(count=Count('role'))
for item in role_counts:
    print(f"  {item['role']}: {item['count']} users")
print()
