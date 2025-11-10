#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from meat_trace.models import User, UserProfile, ProcessingUnit, Shop

print("=" * 80)
print("ALL PROCESSOR USERS")
print("=" * 80)

processors = User.objects.filter(profile__role='Processor')
if processors.count() == 0:
    print("❌ No processor users found")
else:
    print(f"\nFound {processors.count()} processor user(s):\n")
    for user in processors:
        print(f"Username: {user.username}")
        print(f"  Email: {user.email}")
        if user.profile.processing_unit:
            print(f"  Processing Unit: {user.profile.processing_unit.name}")
        else:
            print(f"  ⚠️ No processing unit assigned")
        print()

print("\n" + "=" * 80)
print("ALL USERS IN SYSTEM")
print("=" * 80)
all_users = User.objects.all()
for user in all_users:
    role = user.profile.role if hasattr(user, 'profile') else 'No profile'
    print(f"- {user.username} (Role: {role})")

print("\n" + "=" * 80)
print("AVAILABLE SHOPS")
print("=" * 80)
shops = Shop.objects.all()
if shops.count() == 0:
    print("❌ No shops found")
    print("\nRun: python create_test_shop.py")
else:
    print(f"\nFound {shops.count()} shop(s):\n")
    for shop in shops:
        print(f"- {shop.name} (ID: {shop.id})")
        print(f"  Location: {shop.location}")
        print(f"  Active: {shop.is_active}")
        print()
