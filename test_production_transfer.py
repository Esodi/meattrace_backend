#!/usr/bin/env python
"""
Test transfer to production server
"""
import requests
import json

PROD_URL = 'https://dev.shambabora.co.tz'

print("=" * 80)
print("TESTING PRODUCTION SERVER TRANSFER")
print("=" * 80)

# Step 1: Login to production
print("\n📝 Step 1: Login to production as 'bbb'...")
try:
    login_response = requests.post(
        f'{PROD_URL}/api/v2/auth/login/',
        json={
            'username': 'bbb',
            'password': 'bbbbbb'
        }
    )
    
    print(f"Login Status: {login_response.status_code}")
    
    if login_response.status_code != 200:
        print(f"❌ Login failed!")
        print(f"Response: {login_response.text}")
        exit(1)
    
    login_data = login_response.json()
    print(f"✅ Login successful!")
    print(f"Response keys: {login_data.keys()}")
    
    # Get token (could be 'token', 'access', or 'access_token')
    token = login_data.get('access') or login_data.get('token') or login_data.get('access_token')
    
    if not token:
        print(f"❌ No token found in response: {login_data}")
        exit(1)
    
    print(f"Token: {token[:50]}...")
    
except Exception as e:
    print(f"❌ Error during login: {e}")
    exit(1)

# Step 2: Get products
print("\n📦 Step 2: Getting products from production...")
headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

try:
    products_response = requests.get(
        f'{PROD_URL}/api/v2/products/',
        headers=headers
    )
    
    print(f"Products Status: {products_response.status_code}")
    
    if products_response.status_code != 200:
        print(f"❌ Failed to get products: {products_response.text}")
        exit(1)
    
    products_data = products_response.json()
    if isinstance(products_data, dict) and 'results' in products_data:
        products = products_data['results']
    else:
        products = products_data
    
    available = [p for p in products if p.get('transferred_to') is None]
    print(f"✅ Found {len(products)} total products, {len(available)} available for transfer")
    
    if available:
        print("\nAvailable products:")
        for p in available[:3]:
            print(f"  - {p['name']} (ID: {p['id']}, Batch: {p['batch_number']})")
    
except Exception as e:
    print(f"❌ Error getting products: {e}")
    exit(1)

# Step 3: Get shops
print("\n🏪 Step 3: Getting shops from production...")
try:
    shops_response = requests.get(
        f'{PROD_URL}/api/v2/shops/',
        headers=headers
    )
    
    print(f"Shops Status: {shops_response.status_code}")
    
    if shops_response.status_code != 200:
        print(f"❌ Failed to get shops: {shops_response.text}")
        exit(1)
    
    shops_data = shops_response.json()
    if isinstance(shops_data, dict) and 'results' in shops_data:
        shops = shops_data['results']
    else:
        shops = shops_data
    
    print(f"✅ Found {len(shops)} shops")
    
    if shops:
        print("\nAvailable shops:")
        for s in shops[:3]:
            print(f"  - {s.get('name', 'No name')} (ID: {s['id']})")
    
except Exception as e:
    print(f"❌ Error getting shops: {e}")
    exit(1)

# Step 4: Try to transfer
if not available or not shops:
    print("\n⚠️ Cannot test transfer - no products or shops available")
    exit(0)

print("\n📤 Step 4: Testing transfer...")
transfer_payload = {
    'shop_id': shops[0]['id'],
    'transfers': [
        {
            'product_id': available[0]['id']
        }
    ]
}

print(f"Transfer payload: {json.dumps(transfer_payload, indent=2)}")

try:
    transfer_response = requests.post(
        f'{PROD_URL}/api/v2/products/transfer/',
        headers=headers,
        json=transfer_payload
    )
    
    print(f"\nTransfer Status: {transfer_response.status_code}")
    print(f"Response: {transfer_response.text}")
    
    if transfer_response.status_code == 200:
        print("\n✅ ✅ ✅ TRANSFER SUCCESSFUL! ✅ ✅ ✅")
    elif transfer_response.status_code == 403:
        print("\n❌ FORBIDDEN ERROR!")
        print("Possible causes:")
        print("1. User 'bbb' doesn't exist on production server")
        print("2. User 'bbb' doesn't have 'Processor' role on production")
        print("3. User 'bbb' isn't assigned to a processing unit on production")
        print("4. Token authentication is not working properly")
    else:
        print(f"\n❌ TRANSFER FAILED with status {transfer_response.status_code}")
        
except Exception as e:
    print(f"❌ Error during transfer: {e}")

print("\n" + "=" * 80)
