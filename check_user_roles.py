"""
Check all user roles in the system
"""
import os
import django
import sys

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from django.contrib.auth.models import User
from meat_trace.models import UserProfile, ProcessingUnit

print("=" * 80)
print("USER ROLES IN THE SYSTEM")
print("=" * 80)
print()

# Get all users
all_users = User.objects.all()
print(f"Total users in system: {all_users.count()}")
print()

# Get users with profiles
users_with_profiles = UserProfile.objects.all()
print(f"Users with profiles: {users_with_profiles.count()}")
print()

# Group by role
print("USERS BY ROLE:")
print("-" * 80)
for profile in users_with_profiles:
    print(f"User: {profile.user.username}")
    print(f"  - Role: {profile.role}")
    print(f"  - Processing Unit: {profile.processing_unit}")
    print(f"  - Shop: {profile.shop}")
    print(f"  - Active: {profile.user.is_active}")
    print()

# Count by role
from django.db.models import Count
role_counts = UserProfile.objects.values('role').annotate(count=Count('role'))
print("\nROLE STATISTICS:")
print("-" * 80)
for item in role_counts:
    print(f"  {item['role']}: {item['count']} users")
print()

# Check Processing Unit associations
print("\nPROCESSING UNIT ASSOCIATIONS:")
print("-" * 80)
pu_users = UserProfile.objects.filter(processing_unit__isnull=False)
for profile in pu_users:
    print(f"  {profile.user.username} → {profile.processing_unit.name} (Role: {profile.role})")
print()

# Suggested fix
print("=" * 80)
print("SOLUTION")
print("=" * 80)
print()
print("The users associated with processing units need their role changed to 'Processor'.")
print()
print("Run one of these commands to fix:")
print()
for profile in pu_users:
    if profile.role != 'Processor':
        print(f"  # Fix {profile.user.username}")
        print(f"  python manage.py shell -c \"from meat_trace.models import UserProfile; p = UserProfile.objects.get(user__username='{profile.user.username}'); p.role = 'Processor'; p.save(); print('✅ Updated {profile.user.username} to Processor')\"")
        print()
