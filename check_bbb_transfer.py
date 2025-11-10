#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from meat_trace.models import User, UserProfile, ProcessingUnit, Shop, Product

print("=" * 80)
print("CHECKING BBB USER & TRANSFER CAPABILITY")
print("=" * 80)

# Check user
user = User.objects.filter(username='bbb').first()
if not user:
    print("❌ User 'bbb' not found")
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

# Check products
all_products = Product.objects.filter(processing_unit=processing_unit)
available_products = Product.objects.filter(
    processing_unit=processing_unit,
    transferred_to__isnull=True
)
transferred_products = Product.objects.filter(
    processing_unit=processing_unit,
    transferred_to__isnull=False
)

print(f"\n📦 PRODUCTS OVERVIEW:")
print(f"   Total products: {all_products.count()}")
print(f"   Available for transfer: {available_products.count()}")
print(f"   Already transferred: {transferred_products.count()}")

if available_products.count() > 0:
    print(f"\n   Available products (ready to transfer):")
    for p in available_products[:10]:
        print(f"   - {p.name} (ID: {p.id}, Batch: {p.batch_number}, Qty: {p.quantity})")
else:
    print("\n   ❌ No products available for transfer!")
    if transferred_products.count() > 0:
        print(f"\n   Recently transferred products:")
        for p in transferred_products[:5]:
            shop_name = p.transferred_to.name if p.transferred_to else 'Unknown'
            print(f"   - {p.name} → {shop_name}")

# Check shops
shops = Shop.objects.filter(is_active=True)
print(f"\n🏪 SHOPS:")
print(f"   Available shops: {shops.count()}")
if shops.count() > 0:
    for s in shops[:10]:
        print(f"   - {s.name} (ID: {s.id}, Location: {s.location})")
else:
    print("   ❌ No shops available!")

# Summary
print("\n" + "=" * 80)
print("DIAGNOSIS & SOLUTION")
print("=" * 80)

issues = []
solutions = []

if available_products.count() == 0 and all_products.count() == 0:
    issues.append("No products created")
    solutions.append("Create products first in your processing unit")
elif available_products.count() == 0 and transferred_products.count() > 0:
    issues.append("All products have already been transferred")
    solutions.append("Create new products to transfer more items")
    
if shops.count() == 0:
    issues.append("No shops available")
    solutions.append("Run: python create_test_shop.py")

if not issues:
    print("✅ EVERYTHING LOOKS GOOD!")
    print(f"\n   You have:")
    print(f"   - {available_products.count()} products ready to transfer")
    print(f"   - {shops.count()} shops available as destinations")
    print(f"\n   You should be able to transfer products from the app.")
    print(f"\n   If transfer still fails, check:")
    print(f"   1. App is connected to correct backend URL")
    print(f"   2. You're logged in with username: bbb")
    print(f"   3. Check app console/logs for error messages")
else:
    print("❌ ISSUES FOUND:")
    for i, issue in enumerate(issues, 1):
        print(f"   {i}. {issue}")
    print(f"\n💡 SOLUTIONS:")
    for i, solution in enumerate(solutions, 1):
        print(f"   {i}. {solution}")
