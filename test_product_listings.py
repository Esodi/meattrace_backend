#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from meat_trace.models import Product, ProductInfo

def test_product_listings():
    """Test that product names are consistent across different listings"""

    print("=== Testing Product Listings Consistency ===\n")

    # Test 1: Check Product model names
    products = Product.objects.all()
    print(f"1. Product Model ({products.count()} products):")
    for p in products:
        print(f"   {p.id}: '{p.name}' - {p.product_type}")
    print()

    # Test 2: Check ProductInfo model names (if exists)
    try:
        product_infos = ProductInfo.objects.all()
        print(f"2. ProductInfo Model ({product_infos.count()} products):")
        for pi in product_infos:
            print(f"   {pi.product.id}: '{pi.product_name}' - {pi.product_type}")
        print()
    except Exception as e:
        print(f"2. ProductInfo Model: Not available or error - {e}\n")

    # Test 3: Check for consistency between Product and ProductInfo
    if ProductInfo.objects.exists():
        print("3. Consistency Check (Product vs ProductInfo):")
        inconsistencies = []
        for product in products:
            try:
                product_info = ProductInfo.objects.get(product=product)
                if product.name != product_info.product_name or product.product_type != product_info.product_type:
                    inconsistencies.append({
                        'product_id': product.id,
                        'product_name': product.name,
                        'product_type': product.product_type,
                        'info_name': product_info.product_name,
                        'info_type': product_info.product_type
                    })
            except ProductInfo.DoesNotExist:
                print(f"   WARNING: Product {product.id} has no ProductInfo record")

        if inconsistencies:
            print("   INCONSISTENCIES FOUND:")
            for inc in inconsistencies:
                print(f"   Product {inc['product_id']}:")
                print(f"     Product: '{inc['product_name']}' - {inc['product_type']}")
                print(f"     ProductInfo: '{inc['info_name']}' - {inc['info_type']}")
        else:
            print("   ✓ All products consistent between Product and ProductInfo models")
        print()

    # Test 4: Check for species information in names
    print("4. Species Information Check:")
    species_keywords = ['cow', 'pig', 'chicken', 'sheep', 'goat', 'cattle']
    products_with_species = 0
    products_without_species = 0

    for p in products:
        name_lower = p.name.lower()
        has_species = any(species in name_lower for species in species_keywords)
        if has_species:
            products_with_species += 1
            print(f"   [OK] {p.id}: '{p.name}' - HAS species info")
        else:
            products_without_species += 1
            print(f"   [MISSING] {p.id}: '{p.name}' - MISSING species info")

    print(f"\n   Summary: {products_with_species} with species, {products_without_species} without species")

    # Test 5: Check for "meat" keyword usage
    print("\n5. 'Meat' Keyword Usage:")
    meat_products = products.filter(product_type='meat')
    print(f"   Total meat products: {meat_products.count()}")

    for p in meat_products:
        if 'meat' in p.name.lower():
            print(f"   [HAS_MEAT] {p.id}: '{p.name}' - Contains 'meat'")
        else:
            print(f"   [NO_MEAT] {p.id}: '{p.name}' - No 'meat' in name")

    print("\n=== Test Complete ===")

if __name__ == '__main__':
    test_product_listings()