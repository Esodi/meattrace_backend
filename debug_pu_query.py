#!/usr/bin/env python
"""
Debug what processing units the view is actually querying
"""
import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from django.contrib.auth.models import User
from meat_trace.models import ProcessingUnitUser, Product

def debug_pu_query():
    """Debug processing unit query logic"""
    
    print("\n" + "="*60)
    print("  DEBUGGING PROCESSING UNIT QUERY")
    print("="*60)
    
    user = User.objects.get(username='bbb')
    
    # Replicate the view's logic
    user_processing_units = ProcessingUnitUser.objects.filter(
        user=user,
        is_active=True,
        is_suspended=False
    ).values_list('processing_unit_id', flat=True)
    
    print(f"\nUser: {user.username}")
    print(f"Processing Unit IDs from ProcessingUnitUser: {list(user_processing_units)}")
    
    # Query products using these IDs
    products_from_view_logic = Product.objects.filter(
        processing_unit_id__in=user_processing_units
    )
    
    print(f"\nProducts using view's logic (processing_unit_id__in):")
    print(f"  Total: {products_from_view_logic.count()}")
    for p in products_from_view_logic:
        print(f"  - {p.name}: PU ID={p.processing_unit_id}, Transferred={p.transferred_to is not None}")
    
    # Count in stock using view's logic
    in_stock_from_view = Product.objects.filter(
        processing_unit_id__in=user_processing_units,
        transferred_to__isnull=True
    ).count()
    
    print(f"\nIn Stock (view's logic): {in_stock_from_view}")
    
    # Compare with direct query
    pu = user.profile.processing_unit
    print(f"\nDirect query using UserProfile.processing_unit (ID: {pu.id}):")
    products_direct = Product.objects.filter(processing_unit=pu)
    print(f"  Total: {products_direct.count()}")
    
    in_stock_direct = Product.objects.filter(
        processing_unit=pu,
        transferred_to__isnull=True
    ).count()
    print(f"  In Stock: {in_stock_direct}")

if __name__ == '__main__':
    try:
        debug_pu_query()
    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
