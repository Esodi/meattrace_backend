#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from meat_trace.models import Product

def check_product_names():
    """Check current product names and product types"""
    products = Product.objects.all()
    print(f"Total products: {products.count()}")

    print("\nFirst 10 products:")
    for p in products[:10]:
        print(f"{p.id}: '{p.name}' - {p.product_type}")

    print("\nProducts with 'meat' in name:")
    meat_products = products.filter(name__icontains='meat')
    for p in meat_products:
        print(f"{p.id}: '{p.name}' - {p.product_type}")

    print(f"\nTotal products with 'meat' in name: {meat_products.count()}")

    # Check for products that need updating (generic "meat" names)
    generic_meat_products = []
    for p in products:
        if p.product_type == 'meat' and 'meat' in p.name.lower():
            # Check if it's just "meat" or has descriptors
            name_lower = p.name.lower()
            if name_lower.strip() == 'meat' or name_lower.strip() == 'fresh meat':
                generic_meat_products.append(p)

    print(f"\nProducts that need updating (generic 'meat' names): {len(generic_meat_products)}")
    for p in generic_meat_products:
        print(f"{p.id}: '{p.name}' - {p.product_type}")

if __name__ == '__main__':
    check_product_names()