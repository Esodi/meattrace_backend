#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script to create a test shop for product transfer testing.
Run this from the meattrace_backend directory:
    python create_test_shop.py
"""
import os
import sys
import django

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from meat_trace.models import Shop, ShopUser, User, UserProfile
from django.utils import timezone

def create_test_shop():
    """Create a test shop and shop user for testing product transfers"""
    
    print("=" * 80)
    print("Creating Test Shop for Product Transfer Testing")
    print("=" * 80)
    
    # Check if shop already exists
    shop, created = Shop.objects.get_or_create(
        name='Test Butcher Shop',
        defaults={
            'description': 'A test shop for product transfer testing',
            'location': 'Dar es Salaam, Tanzania',
            'contact_email': 'shop@test.com',
            'contact_phone': '+255 123 456 789',
            'business_license': 'BL-2024-001',
            'tax_id': 'TAX-001',
            'is_active': True,
        }
    )
    
    if created:
        print(f"[OK] Created new shop: {shop.name} (ID: {shop.id})")
    else:
        print(f"[INFO] Shop already exists: {shop.name} (ID: {shop.id})")
    
    # Create or get shop user
    shop_user, user_created = User.objects.get_or_create(
        username='shopuser',
        defaults={
            'email': 'shopuser@test.com',
            'first_name': 'Shop',
            'last_name': 'User',
        }
    )
    
    if user_created:
        shop_user.set_password('password123')
        shop_user.save()
        print(f"[OK] Created new shop user: {shop_user.username} (ID: {shop_user.id})")
    else:
        print(f"[INFO] Shop user already exists: {shop_user.username} (ID: {shop_user.id})")
    
    # Update or create user profile
    profile, profile_created = UserProfile.objects.get_or_create(
        user=shop_user,
        defaults={
            'role': 'shop',
            'shop': shop,
            'phone': '+255 123 456 789',
            'is_profile_complete': True,
        }
    )
    
    if not profile_created:
        profile.role = 'shop'
        profile.shop = shop
        profile.is_profile_complete = True
        profile.save()
        print(f"[OK] Updated user profile for {shop_user.username}")
    else:
        print(f"[OK] Created user profile for {shop_user.username}")
    
    # Create or get shop user membership
    shop_membership, membership_created = ShopUser.objects.get_or_create(
        user=shop_user,
        shop=shop,
        defaults={
            'role': 'owner',
            'permissions': 'admin',
            'is_active': True,
            'joined_at': timezone.now(),
        }
    )
    
    if membership_created:
        print(f"[OK] Created shop membership for {shop_user.username}")
    else:
        print(f"[INFO] Shop membership already exists for {shop_user.username}")
    
    print("\n" + "=" * 80)
    print("Test Shop Setup Complete!")
    print("=" * 80)
    print(f"\nShop Details:")
    print(f"  Name: {shop.name}")
    print(f"  ID: {shop.id}")
    print(f"  Location: {shop.location}")
    print(f"  Phone: {shop.contact_phone}")
    print(f"  Active: {shop.is_active}")
    print(f"\nShop User Credentials:")
    print(f"  Username: {shop_user.username}")
    print(f"  Password: password123")
    print(f"  Email: {shop_user.email}")
    print(f"  Role: {profile.role}")
    print("\nYou can now:")
    print("  1. Login as processing unit user to transfer products")
    print("  2. Login as 'shopuser' to receive products")
    print("=" * 80)

if __name__ == '__main__':
    create_test_shop()