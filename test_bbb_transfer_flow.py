#!/usr/bin/env python
"""
Test the complete product transfer flow for user 'bbb'
This simulates what the mobile app does
"""
import os
import django
import requests
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from django.contrib.auth.models import User
from meat_trace.models import Product, Shop

BASE_URL = 'http://localhost:8000'  # Change if your server runs on different port

print("=" * 80)
print("TESTING PRODUCT TRANSFER FLOW FOR USER 'bbb'")
print("=" * 80)

# Step 1: Login
print("\n📝 Step 1: Attempting to login as 'bbb'...")
login_response = requests.post(
    f'{BASE_URL}/api/v2/auth/login/',
    json={
        'username': 'bbb',
        'password': 'bbbbbb'
    }
)

if login_response.status_code != 200:
    print(f"❌ Login failed: {login_response.status_code}")
    print(f"Response: {login_response.text}")
    exit(1)

login_data = login_response.json()
token = login_data.get('token') or login_data.get('tokens', {}).get('access')
if not token:
    print(f"❌ No token in response: {login_data}")
    exit(1)

print(f"✅ Login successful! Token: {token[:20]}...")

headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

# Step 2: Get products available for transfer
print("\n📦 Step 2: Fetching products...")
products_response = requests.get(
    f'{BASE_URL}/api/v2/products/',
    headers=headers
)

if products_response.status_code != 200:
    print(f"❌ Failed to fetch products: {products_response.status_code}")
    print(f"Response: {products_response.text}")
    exit(1)

products_data = products_response.json()
if isinstance(products_data, dict) and 'results' in products_data:
    products = products_data['results']
else:
    products = products_data

# Filter for products not yet transferred
available_products = [p for p in products if p.get('transferred_to') is None]

print(f"✅ Found {len(products)} total products")
print(f"   Available for transfer: {len(available_products)}")

if not available_products:
    print("❌ No products available for transfer!")
    print("\nExisting products status:")
    for p in products[:5]:
        status = "Transferred" if p.get('transferred_to') else "Available"
        print(f"  - {p['name']} (ID: {p['id']}) - {status}")
    exit(1)

print("\nAvailable products:")
for p in available_products[:5]:
    print(f"  - {p['name']} (ID: {p['id']}, Batch: {p['batch_number']}, Qty: {p['quantity']})")

# Step 3: Get shops
print("\n🏪 Step 3: Fetching shops...")
shops_response = requests.get(
    f'{BASE_URL}/api/v2/shops/',
    headers=headers
)

if shops_response.status_code != 200:
    print(f"❌ Failed to fetch shops: {shops_response.status_code}")
    print(f"Response: {shops_response.text}")
    exit(1)

shops_data = shops_response.json()
if isinstance(shops_data, dict) and 'results' in shops_data:
    shops = shops_data['results']
else:
    shops = shops_data

print(f"✅ Found {len(shops)} shops")

if not shops:
    print("❌ No shops available!")
    exit(1)

print("\nAvailable shops:")
for s in shops:
    print(f"  - {s.get('name', 'No name')} (ID: {s['id']}, Location: {s.get('location', 'N/A')})")

# Step 4: Transfer first product to first shop
print("\n📤 Step 4: Transferring product...")
product_to_transfer = available_products[0]
shop_to_transfer_to = shops[0]

print(f"   Product: {product_to_transfer['name']} (ID: {product_to_transfer['id']})")
print(f"   To Shop: {shop_to_transfer_to.get('name', 'No name')} (ID: {shop_to_transfer_to['id']})")

transfer_payload = {
    'shop_id': shop_to_transfer_to['id'],
    'transfers': [
        {
            'product_id': product_to_transfer['id']
        }
    ]
}

print(f"\nTransfer payload:")
print(json.dumps(transfer_payload, indent=2))

transfer_response = requests.post(
    f'{BASE_URL}/api/v2/products/transfer/',
    headers=headers,
    json=transfer_payload
)

print(f"\nResponse status: {transfer_response.status_code}")
print(f"Response body:")
print(json.dumps(transfer_response.json(), indent=2))

if transfer_response.status_code == 200:
    print("\n✅ ✅ ✅ TRANSFER SUCCESSFUL! ✅ ✅ ✅")
else:
    print(f"\n❌ ❌ ❌ TRANSFER FAILED! ❌ ❌ ❌")
    print(f"Status: {transfer_response.status_code}")
    print(f"Error: {transfer_response.text}")

# Step 5: Verify transfer in database
print("\n🔍 Step 5: Verifying in database...")
product = Product.objects.get(id=product_to_transfer['id'])
if product.transferred_to:
    print(f"✅ Product transferred to: {product.transferred_to.name}")
    print(f"   Transferred at: {product.transferred_at}")
else:
    print(f"❌ Product NOT transferred in database!")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
