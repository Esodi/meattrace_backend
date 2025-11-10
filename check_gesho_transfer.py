#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from meat_trace.models import User, UserProfile, ProcessingUnit, Shop, Product

print("=" * 80)
print("CHECKING GESHO USER & TRANSFER CAPABILITY")
print("=" * 80)

# Check user
user = User.objects.filter(username='Gesho').first()
if not user:
    print("❌ User 'Gesho' not found")
    exit()

print(f"\n✅ User found: {user.username}")
print(f"   Email: {user.email}")

# Check profile
if not hasattr(user, 'profile'):
    print("❌ User has no profile")
    exit()

profile = user.profile
print(f"   Role: {profile.role}")

# Check processing unit
if profile.role != 'Processor':
    print(f"❌ User role is '{profile.role}', not 'Processor'")
    print("   Only users with 'Processor' role can transfer products")
    exit()

if not profile.processing_unit:
    print("❌ User has no processing unit assigned")
    exit()

processing_unit = profile.processing_unit
print(f"\n✅ Processing Unit: {processing_unit.name}")
print(f"   Location: {processing_unit.location}")
print(f"   Active: {processing_unit.is_active}")

# Check products
products = Product.objects.filter(
    processing_unit=processing_unit,
    transferred_to__isnull=True
)
print(f"\n📦 Available products for transfer: {products.count()}")
if products.count() > 0:
    for p in products[:5]:
        print(f"   - {p.name} (ID: {p.id}, Batch: {p.batch_number}, Qty: {p.quantity})")

# Check shops
shops = Shop.objects.filter(is_active=True)
print(f"\n🏪 Available shops: {shops.count()}")
if shops.count() > 0:
    for s in shops[:5]:
        print(f"   - {s.name} (ID: {s.id}, Location: {s.location})")
else:
    print("   ❌ No shops available!")
    print("   You need to create at least one shop to transfer products.")

# Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

if products.count() == 0:
    print("❌ PROBLEM: No products available to transfer")
    print("   Create products first at your processing unit")
elif shops.count() == 0:
    print("❌ PROBLEM: No shops available for transfer")
    print("   Solution: Run 'python create_test_shop.py' to create a test shop")
else:
    print("✅ Everything looks good!")
    print(f"   - You have {products.count()} products ready to transfer")
    print(f"   - You have {shops.count()} shops available")
    print("\nYou should be able to transfer products from the app.")
    print("If you still can't transfer, check:")
    print("  1. The app is connected to the backend (check API endpoint)")
    print("  2. You're logged in with correct credentials")
    print("  3. Check the app logs for any errors")
