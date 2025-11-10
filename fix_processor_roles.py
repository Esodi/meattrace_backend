"""
Fix processor user roles from 'processing_unit' to 'Processor'
This will allow them to transfer products to shops
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
print("FIXING PROCESSOR USER ROLES")
print("=" * 80)
print()

# Get users with processing_unit role
users_to_fix = UserProfile.objects.filter(role='processing_unit')
print(f"Found {users_to_fix.count()} users with role 'processing_unit'")
print()

if users_to_fix.count() == 0:
    print("✅ No users to fix!")
else:
    print("Updating roles to 'Processor':")
    print("-" * 80)
    for profile in users_to_fix:
        old_role = profile.role
        profile.role = 'Processor'
        profile.save()
        print(f"  ✅ {profile.user.username}: '{old_role}' → 'Processor' (PU: {profile.processing_unit})")
    
    print()
    print("=" * 80)
    print("✅ ALL ROLES UPDATED SUCCESSFULLY!")
    print("=" * 80)
    print()
    print("Users can now transfer products from processor to shop.")
    print()
    
    # Verify
    processors = UserProfile.objects.filter(role='Processor')
    print(f"Total Processor users now: {processors.count()}")
    for p in processors:
        print(f"  - {p.user.username} (PU: {p.processing_unit})")
