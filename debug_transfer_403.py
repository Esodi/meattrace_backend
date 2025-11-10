"""
Debug script for 403 Forbidden error on /api/v2/products/transfer/
Run this to diagnose the issue in production.
"""
import os
import django
import sys

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from django.contrib.auth.models import User
from meat_trace.models import UserProfile, ProcessingUnit, Product, Shop
from rest_framework_simplejwt.tokens import AccessToken
from datetime import datetime

print("=" * 80)
print("DEBUGGING 403 FORBIDDEN ERROR ON /api/v2/products/transfer/")
print("=" * 80)
print()

# Check if there are any processor users
print("1. CHECKING PROCESSOR USERS:")
print("-" * 80)
processors = UserProfile.objects.filter(role='Processor')
print(f"Total Processor users: {processors.count()}")
for profile in processors[:5]:  # Show first 5
    user = profile.user
    print(f"  ✓ User: {user.username} (ID: {user.id})")
    print(f"    - Email: {user.email}")
    print(f"    - Active: {user.is_active}")
    print(f"    - Processing Unit: {profile.processing_unit}")
    
    # Generate a fresh token for this user
    token = AccessToken.for_user(user)
    print(f"    - Fresh JWT Token: {token}")
    print()

if processors.count() == 0:
    print("  ⚠️  WARNING: No Processor users found!")
    print()

# Check processing units
print("2. CHECKING PROCESSING UNITS:")
print("-" * 80)
units = ProcessingUnit.objects.all()
print(f"Total Processing Units: {units.count()}")
for unit in units[:5]:
    print(f"  ✓ {unit.name} (ID: {unit.id})")
    # Count products for this unit
    product_count = Product.objects.filter(processing_unit=unit).count()
    print(f"    - Products: {product_count}")
    # Count users
    user_count = UserProfile.objects.filter(processing_unit=unit).count()
    print(f"    - Users: {user_count}")
    print()

# Check shops
print("3. CHECKING SHOPS (Transfer Destinations):")
print("-" * 80)
shops = Shop.objects.all()
print(f"Total Shops: {shops.count()}")
for shop in shops[:5]:
    print(f"  ✓ {shop.name} (ID: {shop.id})")
    if hasattr(shop, 'location'):
        print(f"    - Location: {shop.location}")
    print()

if shops.count() == 0:
    print("  ⚠️  WARNING: No Shops found!")
    print()

# Check transferable products
print("4. CHECKING TRANSFERABLE PRODUCTS:")
print("-" * 80)
transferable = Product.objects.filter(transferred_to__isnull=True)
print(f"Total products available for transfer: {transferable.count()}")
for product in transferable[:5]:
    print(f"  ✓ {product.name} (ID: {product.id})")
    print(f"    - Processing Unit: {product.processing_unit}")
    print(f"    - Quantity: {product.quantity}")
    print(f"    - Already transferred: {product.transferred_to is not None}")
    print()

# Check products that were already transferred
already_transferred = Product.objects.filter(transferred_to__isnull=False)
print(f"Products already transferred: {already_transferred.count()}")
print()

# Provide test curl command
print("5. TEST COMMAND FOR PRODUCTION:")
print("-" * 80)
if processors.count() > 0 and shops.count() > 0 and transferable.count() > 0:
    test_processor = processors.first()
    test_shop = shops.first()
    test_product = transferable.filter(processing_unit=test_processor.processing_unit).first()
    
    if test_product:
        test_token = AccessToken.for_user(test_processor.user)
        
        print("Copy and run this curl command in your production environment:")
        print()
        print(f"curl -X POST https://dev.shambabora.co.tz/api/v2/products/transfer/ \\")
        print(f"  -H 'Authorization: Bearer {test_token}' \\")
        print(f"  -H 'Content-Type: application/json' \\")
        print(f"  -d '{{")
        print(f"    \"shop_id\": {test_shop.id},")
        print(f"    \"transfers\": [")
        print(f"      {{\"product_id\": {test_product.id}, \"quantity\": 1.0}}")
        print(f"    ]")
        print(f"  }}'")
        print()
        print(f"Test User: {test_processor.user.username}")
        print(f"Test Shop: {test_shop.name}")
        print(f"Test Product: {test_product.name}")
    else:
        print("⚠️  No products found for the processor's processing unit")
else:
    print("⚠️  Cannot generate test command: Missing processors, shops, or products")

print()
print("6. COMMON 403 FORBIDDEN CAUSES:")
print("-" * 80)
print("  1. Token expired - Generate fresh token above")
print("  2. User role is not 'Processor' - Check user roles above")
print("  3. User not associated with ProcessingUnit - Check user details above")
print("  4. Products don't belong to user's processing unit")
print("  5. Products already transferred (transferred_to is not null)")
print("  6. CORS issues in production (check browser console)")
print("  7. Wrong Authorization header format (must be 'Bearer <token>')")
print()

print("7. NEXT STEPS:")
print("-" * 80)
print("  A. If testing from browser/app:")
print("     - Check browser DevTools Network tab")
print("     - Look for Authorization header in request")
print("     - Check response body for detailed error message")
print()
print("  B. If testing from curl:")
print("     - Use the curl command generated above")
print("     - Add -v flag for verbose output")
print("     - Check response status and body")
print()
print("  C. Check production logs:")
print("     - Look for Django error messages")
print("     - Check authentication failures")
print("     - Review permission denied logs")
print()

print("=" * 80)
print("DEBUG COMPLETE")
print("=" * 80)
