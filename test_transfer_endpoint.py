"""
Test script for the product transfer endpoint with quantity adjustment
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from django.contrib.auth.models import User
from meat_trace.models import Product, Shop, ProcessingUnit, UserProfile
from rest_framework.test import APIClient

def test_transfer_endpoint():
    """Test the transfer endpoint with and without quantity adjustment"""
    
    # Setup
    client = APIClient()
    
    # Get a processor user
    try:
        processor_user = User.objects.filter(profile__role='Processor').first()
        if not processor_user:
            print("❌ No processor user found")
            return
        
        print(f"✅ Found processor user: {processor_user.username}")
        
        # Get processing unit
        processing_unit = processor_user.profile.processing_unit
        if not processing_unit:
            print("❌ Processor has no processing unit")
            return
        
        print(f"✅ Processing unit: {processing_unit.name}")
        
        # Get a product
        product = Product.objects.filter(
            processing_unit=processing_unit,
            transferred_to__isnull=True
        ).first()
        
        if not product:
            print("❌ No available products for transfer")
            return
        
        print(f"✅ Found product: {product.name} (Qty: {product.quantity})")
        
        # Get a shop
        shop = Shop.objects.first()
        if not shop:
            print("❌ No shops available")
            return
        
        print(f"✅ Found shop: {shop.name}")
        
        # Login
        client.force_authenticate(user=processor_user)
        
        # Test 1: Transfer with partial quantity
        print("\n=== Test 1: Partial Quantity Transfer ===")
        partial_qty = product.quantity / 2
        
        response = client.post('/api/v2/products/transfer/', {
            'shop_id': shop.id,
            'transfers': [
                {
                    'product_id': product.id,
                    'quantity': partial_qty
                }
            ]
        }, format='json')
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.data}")
        
        if response.status_code == 200:
            print("✅ Partial transfer successful!")
            
            # Verify the original product quantity was reduced
            product.refresh_from_db()
            print(f"Original product quantity after transfer: {product.quantity}")
            
            # Check for the new transferred product
            transferred_product = Product.objects.filter(
                batch_number__contains=f"{product.batch_number.split('-')[0]}-T"
            ).first()
            
            if transferred_product:
                print(f"✅ New transferred product created:")
                print(f"   - Batch: {transferred_product.batch_number}")
                print(f"   - Quantity: {transferred_product.quantity}")
                print(f"   - Transferred to: {transferred_product.transferred_to.name}")
        else:
            print(f"❌ Transfer failed: {response.data}")
        
        print("\n=== Test 2: Full Quantity Transfer (Legacy) ===")
        # Get another product
        product2 = Product.objects.filter(
            processing_unit=processing_unit,
            transferred_to__isnull=True
        ).exclude(id=product.id).first()
        
        if product2:
            response = client.post('/api/v2/products/transfer/', {
                'shop_id': shop.id,
                'product_ids': [product2.id]  # Legacy format
            }, format='json')
            
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.data}")
            
            if response.status_code == 200:
                print("✅ Full transfer successful!")
                product2.refresh_from_db()
                print(f"Product transferred to: {product2.transferred_to.name if product2.transferred_to else 'None'}")
            else:
                print(f"❌ Transfer failed: {response.data}")
        else:
            print("⚠️ No second product available for full transfer test")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_transfer_endpoint()
