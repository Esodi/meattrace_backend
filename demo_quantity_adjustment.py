"""
Quick demonstration of the quantity adjustment feature
"""
import requests
import json

BASE_URL = 'http://localhost:8000'

# Login as processor
print("🔐 Logging in as processor...")
response = requests.post(
    f'{BASE_URL}/api/v2/token/',
    json={'username': 'bbb', 'password': 'bbbbbb'}
)
token = response.json()['access']
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

# Get products
print("\n📦 Fetching available products...")
response = requests.get(f'{BASE_URL}/api/v2/products/', headers=headers)
products = response.json()
if isinstance(products, dict) and 'results' in products:
    products = products['results']

available = [p for p in products if p.get('transferred_to') is None]
print(f"Found {len(available)} available products")

if not available:
    print("⚠️  No products available. Create some products first!")
    exit()

# Get shops
response = requests.get(f'{BASE_URL}/api/v2/shops/', headers=headers)
shops = response.json()
if isinstance(shops, dict) and 'results' in shops:
    shops = shops['results']

if not shops:
    print("⚠️  No shops available!")
    exit()

shop_id = shops[0]['id']
shop_name = shops[0].get('name', 'Unknown')

# Demonstrate partial transfer
product = available[0]
total_qty = float(product['quantity'])
transfer_qty = total_qty * 0.7  # Transfer 70%, keep 30%

print(f"\n🎯 DEMONSTRATING PARTIAL TRANSFER")
print(f"Product: {product['name']}")
print(f"Total Quantity: {total_qty}")
print(f"Transferring: {transfer_qty} (70%)")
print(f"Keeping: {total_qty - transfer_qty} (30%)")
print(f"To Shop: {shop_name}")

response = requests.post(
    f'{BASE_URL}/api/v2/products/transfer/',
    headers=headers,
    json={
        'shop_id': shop_id,
        'transfers': [
            {'product_id': product['id'], 'quantity': transfer_qty}
        ]
    }
)

print(f"\n{'='*60}")
if response.status_code == 200:
    result = response.json()
    print(f"✅ SUCCESS!")
    print(f"Message: {result['message']}")
    print(f"Transferred: {result['transferred_count']} product(s)")
    
    # Verify split
    print(f"\n📋 Verifying inventory split...")
    response = requests.get(f'{BASE_URL}/api/v2/products/{product["id"]}/', headers=headers)
    if response.status_code == 200:
        updated = response.json()
        print(f"✅ Original product kept: {updated['quantity']} units")
    
    print(f"\nCheck the shop's pending receipts to see the transferred quantity!")
else:
    print(f"❌ FAILED: {response.status_code}")
    print(response.json())

print(f"{'='*60}")
