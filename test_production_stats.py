#!/usr/bin/env python
"""
Test script for Production Stats endpoint
Tests the production overview statistics for processing unit users
"""
import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from django.contrib.auth.models import User
from meat_trace.models import UserProfile, ProcessingUnit, Animal, Product, TransferRequest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
import json

def print_separator(title=""):
    """Print a formatted separator"""
    if title:
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}")
    else:
        print(f"{'='*60}")

def test_production_stats():
    """Test the production stats endpoint"""
    
    print_separator("PRODUCTION STATS TEST")
    
    # 1. Get the processing unit user
    try:
        user = User.objects.get(username='bbb')
        profile = user.profile
        pu = profile.processing_unit
        
        print(f"\n✓ User found: {user.username}")
        print(f"✓ Profile role: {profile.role}")
        print(f"✓ Processing Unit: {pu.name if pu else 'None'}")
        
        if not pu:
            print("\n✗ ERROR: User does not have a processing unit!")
            return
            
    except User.DoesNotExist:
        print("\n✗ ERROR: User 'bbb' not found!")
        print("Creating test user...")
        user = User.objects.create_user(
            username='bbb',
            password='bbbbbb',
            email='bbb@test.com'
        )
        pu = ProcessingUnit.objects.create(
            name='Test Processing Unit',
            location='Test Location'
        )
        profile = UserProfile.objects.create(
            user=user,
            role='processing_unit',
            processing_unit=pu
        )
        print(f"✓ Created user and processing unit")
    
    # 2. Check database counts
    print_separator("DATABASE COUNTS")
    
    # Count received animals (whole animals)
    from meat_trace.models import SlaughterPart
    received_whole_animals = Animal.objects.filter(
        transferred_to=pu,
        received_at__isnull=False
    ).count()
    
    # Count received slaughter parts
    received_slaughter_parts = SlaughterPart.objects.filter(
        transferred_to=pu,
        received_at__isnull=False
    ).count()
    
    total_received = received_whole_animals + received_slaughter_parts
    print(f"\nReceived Whole Animals: {received_whole_animals}")
    print(f"Received Slaughter Parts: {received_slaughter_parts}")
    print(f"Total Received: {total_received}")
    print(f"  (Animals + Parts transferred to '{pu.name}' and marked as received)")
    
    # Count pending transfers (animals/parts not yet received or rejected)
    pending_whole_animals = Animal.objects.filter(
        transferred_to=pu,
        received_by__isnull=True,
        rejection_status__isnull=True
    ).count()
    
    pending_slaughter_parts = SlaughterPart.objects.filter(
        transferred_to=pu,
        received_by__isnull=True,
        rejection_status__isnull=True
    ).count()
    
    total_pending = pending_whole_animals + pending_slaughter_parts
    print(f"\nPending Whole Animals: {pending_whole_animals}")
    print(f"Pending Slaughter Parts: {pending_slaughter_parts}")
    print(f"Total Pending: {total_pending}")
    print(f"  (Animals/Parts transferred to '{pu.name}' but not yet received or rejected)")
    
    # Count total products
    total_products = Product.objects.filter(
        processing_unit=pu
    ).count()
    print(f"\nTotal Products: {total_products}")
    print(f"  (All products created by '{pu.name}')")
    
    # Count in-stock products
    in_stock_products = Product.objects.filter(
        processing_unit=pu
    ).exclude(
        quantity=0
    ).count()
    print(f"\nIn Stock Products: {in_stock_products}")
    print(f"  (Products with quantity > 0)")
    
    # 3. Test API authentication
    print_separator("API AUTHENTICATION TEST")
    
    client = APIClient()
    
    # Login and get token
    login_data = {
        'username': 'bbb',
        'password': 'bbbbbb'
    }
    
    response = client.post('/api/v2/token/', login_data, format='json')
    
    if response.status_code == 200:
        print(f"\n✓ Login successful")
        token_data = response.json()
        access_token = token_data.get('access')
        print(f"✓ Access token received")
        
        # Check if user data is in response
        if 'user' in token_data:
            print(f"✓ User data included in login response")
            print(f"  Role: {token_data['user'].get('role')}")
            print(f"  Processing Unit: {token_data['user'].get('processing_unit_name', 'N/A')}")
    else:
        print(f"\n✗ Login failed: {response.status_code}")
        print(f"Response: {response.json()}")
        return
    
    # 4. Test production stats endpoint
    print_separator("PRODUCTION STATS ENDPOINT TEST")
    
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
    
    response = client.get('/api/v2/production-stats/')
    
    print(f"\nStatus Code: {response.status_code}")
    
    if response.status_code == 200:
        print(f"✓ Production stats endpoint successful")
        
        stats_data = response.json()
        print(f"\nResponse Data:")
        print(json.dumps(stats_data, indent=2))
        
        # Verify the stats match expected values
        print_separator("VERIFICATION")
        
        expected = {
            'received': total_received,
            'pending': total_pending,
            'products': total_products,
            'in_stock': in_stock_products
        }
        
        actual = {
            'received': stats_data.get('received', 0),
            'pending': stats_data.get('pending', 0),
            'products': stats_data.get('products', 0),
            'in_stock': stats_data.get('in_stock', 0)
        }
        
        all_match = True
        for key in expected:
            match = expected[key] == actual[key]
            symbol = "✓" if match else "✗"
            print(f"\n{symbol} {key.upper()}: Expected {expected[key]}, Got {actual[key]}")
            if not match:
                all_match = False
        
        if all_match:
            print_separator("✓ ALL TESTS PASSED")
        else:
            print_separator("✗ SOME TESTS FAILED")
            
    else:
        print(f"✗ Production stats endpoint failed")
        print(f"Response: {response.json()}")
    
    # 5. Show sample data details if available
    if total_received > 0 or total_products > 0:
        print_separator("SAMPLE DATA")
        
        if total_received > 0:
            print("\nSample Received Animals:")
            animals = Animal.objects.filter(
                transferred_to=pu,
                received_at__isnull=False
            )[:3]
            for animal in animals:
                print(f"  - {animal.animal_id}: {animal.species}, "
                      f"received {animal.received_at.strftime('%Y-%m-%d %H:%M') if animal.received_at else 'N/A'}")
        
        if total_products > 0:
            print("\nSample Products:")
            products = Product.objects.filter(processing_unit=pu)[:3]
            for product in products:
                print(f"  - {product.name}: Quantity {product.quantity}, "
                      f"created {product.created_at.strftime('%Y-%m-%d %H:%M')}")

if __name__ == '__main__':
    try:
        test_production_stats()
    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
