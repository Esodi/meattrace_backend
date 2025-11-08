#!/usr/bin/env python
"""
Debug IN_STOCK count discrepancy
"""
import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from django.contrib.auth.models import User
from meat_trace.models import Product, ProcessingUnit

def debug_in_stock():
    """Debug IN_STOCK count discrepancy"""
    
    print("\n" + "="*60)
    print("  DEBUGGING IN_STOCK COUNT")
    print("="*60)
    
    user = User.objects.get(username='bbb')
    pu = user.profile.processing_unit
    
    print(f"\nProcessing Unit: {pu.name} (ID: {pu.id})")
    
    # Get all products
    all_products = Product.objects.filter(processing_unit=pu)
    print(f"\nTotal Products: {all_products.count()}")
    
    # Method 1: Products with quantity > 0 (what the test expects)
    in_stock_qty = Product.objects.filter(
        processing_unit=pu
    ).exclude(quantity=0).count()
    print(f"\nMethod 1 - Products with quantity > 0: {in_stock_qty}")
    
    # Method 2: Products not transferred (what the view uses)
    in_stock_not_transferred = Product.objects.filter(
        processing_unit=pu,
        transferred_to__isnull=True
    ).count()
    print(f"Method 2 - Products not transferred: {in_stock_not_transferred}")
    
    # Show details of all products
    print("\n" + "="*60)
    print("  ALL PRODUCTS DETAILS")
    print("="*60)
    
    for product in all_products:
        print(f"\nProduct: {product.name}")
        print(f"  Quantity: {product.quantity}")
        print(f"  Transferred To: {product.transferred_to.name if product.transferred_to else 'None'}")
        print(f"  Created: {product.created_at.strftime('%Y-%m-%d %H:%M')}")
    
    # Categorize products
    print("\n" + "="*60)
    print("  CATEGORIZATION")
    print("="*60)
    
    not_transferred = all_products.filter(transferred_to__isnull=True)
    transferred = all_products.exclude(transferred_to__isnull=True)
    
    print(f"\nProducts NOT transferred (transferred_to is NULL):")
    print(f"  Count: {not_transferred.count()}")
    for p in not_transferred:
        print(f"  - {p.name}: Qty={p.quantity}")
    
    print(f"\nProducts TRANSFERRED (transferred_to is NOT NULL):")
    print(f"  Count: {transferred.count()}")
    for p in transferred:
        print(f"  - {p.name}: Qty={p.quantity}, Transferred to: {p.transferred_to.name}")
    
    # Analysis
    print("\n" + "="*60)
    print("  ANALYSIS")
    print("="*60)
    
    print("\nThe discrepancy occurs because:")
    print("- Test expects: Products with quantity > 0")
    print("- View returns: Products not transferred (transferred_to is NULL)")
    print("\nThese are different concepts:")
    print("- A product can have quantity > 0 AND be transferred")
    print("- A product can have quantity = 0 AND not be transferred")
    print("\nThe view's logic is correct for 'IN STOCK' meaning")
    print("'not yet transferred to a shop'")

if __name__ == '__main__':
    try:
        debug_in_stock()
    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
