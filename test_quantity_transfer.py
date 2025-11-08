"""}
Test script for product transfer with quantity adjustment
Tests both full and partial quantity transfers
"""
import requests
import json

BASE_URL = 'http://localhost:8000'

def get_auth_token(username, password):
    """Get authentication token"""
    response = requests.post(
        f'{BASE_URL}/api/v2/token/',
        json={'username': username, 'password': password}
    )
    if response.status_code == 200:
        return response.json()['access']
    else:
        print(f"Failed to authenticate: {response.status_code}")
        print(response.text)
        return None

def test_product_transfer():
    """Test product transfer with quantity adjustment"""
    
    # Login as processor
    print("=" * 60)
    print("TESTING PRODUCT TRANSFER WITH QUANTITY ADJUSTMENT")
    print("=" * 60)
    
    processor_token = get_auth_token('bbb', 'bbbbbb')
    if not processor_token:
        print("❌ Failed to login as processor")
        return
    
    print("✅ Logged in as processor (bbb)")
    
    headers = {
        'Authorization': f'Bearer {processor_token}',
        'Content-Type': 'application/json'
    }
    
    # Get available products
    print("\n📦 Fetching available products...")
    response = requests.get(
        f'{BASE_URL}/api/v2/products/',
        headers=headers
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to fetch products: {response.status_code}")
        print(response.text)
        return
    
    products = response.json()
    if isinstance(products, dict) and 'results' in products:
        products = products['results']
    
    # Filter products not yet transferred
    available_products = [p for p in products if p.get('transferred_to') is None]
    
    print(f"✅ Found {len(available_products)} available products")
    
    if not available_products:
        print("⚠️  No products available for transfer. Please create some products first.")
        return
    
    # Display first few products
    print("\nAvailable Products:")
    for i, p in enumerate(available_products[:5]):
        print(f"  {i+1}. ID: {p['id']}, Name: {p['name']}, Quantity: {p['quantity']}, Batch: {p['batch_number']}")
    
    # Get available shops
    print("\n🏪 Fetching shops...")
    response = requests.get(
        f'{BASE_URL}/api/v2/shops/',
        headers=headers
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to fetch shops: {response.status_code}")
        print(response.text)
        return
    
    shops = response.json()
    if isinstance(shops, dict) and 'results' in shops:
        shops = shops['results']
    
    print(f"✅ Found {len(shops)} shops")
    
    if not shops:
        print("⚠️  No shops available. Cannot test transfer.")
        return
    
    # Display shops
    print("\nAvailable Shops:")
    for i, s in enumerate(shops[:3]):
        print(f"  {i+1}. ID: {s['id']}, Name: {s.get('name', 'N/A')}, Username: {s.get('username', 'N/A')}")
    
    shop_id = shops[0]['id']
    print(f"\n🎯 Selected shop: {shops[0].get('name', shops[0].get('username', 'Unknown'))} (ID: {shop_id})")
    
    # Test 1: Full quantity transfer (legacy format)
    print("\n" + "=" * 60)
    print("TEST 1: FULL QUANTITY TRANSFER (Legacy Format)")
    print("=" * 60)
    
    if len(available_products) >= 1:
        product = available_products[0]
        print(f"Transferring product: {product['name']} (ID: {product['id']}, Qty: {product['quantity']})")
        
        transfer_data = {
            'product_ids': [product['id']],
            'shop_id': shop_id
        }
        
        response = requests.post(
            f'{BASE_URL}/api/v2/products/transfer/',
            headers=headers,
            json=transfer_data
        )
        
        print(f"Response Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("✅ TEST 1 PASSED: Full quantity transfer successful")
        else:
            print("❌ TEST 1 FAILED")
    
    # Test 2: Partial quantity transfer
    print("\n" + "=" * 60)
    print("TEST 2: PARTIAL QUANTITY TRANSFER")
    print("=" * 60)
    
    if len(available_products) >= 2:
        product = available_products[1]
        original_qty = float(product['quantity'])  # Convert to float
        transfer_qty = original_qty / 2  # Transfer half
        
        print(f"Product: {product['name']} (ID: {product['id']})")
        print(f"Original Quantity: {original_qty}")
        print(f"Transferring: {transfer_qty}")
        print(f"Will remain: {original_qty - transfer_qty}")
        
        transfer_data = {
            'shop_id': shop_id,
            'transfers': [
                {
                    'product_id': product['id'],
                    'quantity': transfer_qty
                }
            ]
        }
        
        response = requests.post(
            f'{BASE_URL}/api/v2/products/transfer/',
            headers=headers,
            json=transfer_data
        )
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("✅ TEST 2 PASSED: Partial quantity transfer successful")
            
            # Verify the original product still exists with reduced quantity
            print("\n📋 Verifying original product...")
            response = requests.get(
                f'{BASE_URL}/api/v2/products/{product["id"]}/',
                headers=headers
            )
            
            if response.status_code == 200:
                updated_product = response.json()
                updated_qty = float(updated_product['quantity'])  # Convert to float
                expected_qty = original_qty - transfer_qty
                print(f"Original product quantity: {updated_qty} (expected: {expected_qty})")
                if abs(updated_qty - expected_qty) < 0.01:
                    print("✅ Original product quantity correctly reduced")
                else:
                    print("⚠️  Original product quantity mismatch")
        else:
            print("❌ TEST 2 FAILED")
    
    # Test 3: Multiple products with mixed quantities
    print("\n" + "=" * 60)
    print("TEST 3: MULTIPLE PRODUCTS WITH MIXED QUANTITIES")
    print("=" * 60)
    
    if len(available_products) >= 4:
        transfers = []
        
        # Product 1: Full quantity
        p1 = available_products[2]
        transfers.append({'product_id': p1['id']})
        print(f"1. {p1['name']} - Full quantity: {p1['quantity']}")
        
        # Product 2: Partial (75%)
        p2 = available_products[3]
        p2_qty = float(p2['quantity']) * 0.75  # Convert to float
        transfers.append({'product_id': p2['id'], 'quantity': p2_qty})
        print(f"2. {p2['name']} - Partial: {p2_qty} of {p2['quantity']}")
        
        transfer_data = {
            'shop_id': shop_id,
            'transfers': transfers
        }
        
        response = requests.post(
            f'{BASE_URL}/api/v2/products/transfer/',
            headers=headers,
            json=transfer_data
        )
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("✅ TEST 3 PASSED: Multiple products transfer successful")
        else:
            print("❌ TEST 3 FAILED")
    
    # Test 4: Invalid quantity (exceeds available)
    print("\n" + "=" * 60)
    print("TEST 4: INVALID QUANTITY (Should Fail)")
    print("=" * 60)
    
    if available_products:
        product = available_products[-1]
        invalid_qty = float(product['quantity']) + 100  # Convert to float
        
        print(f"Product: {product['name']} (Available: {product['quantity']})")
        print(f"Attempting to transfer: {invalid_qty} (should fail)")
        
        transfer_data = {
            'shop_id': shop_id,
            'transfers': [
                {
                    'product_id': product['id'],
                    'quantity': invalid_qty
                }
            ]
        }
        
        response = requests.post(
            f'{BASE_URL}/api/v2/products/transfer/',
            headers=headers,
            json=transfer_data
        )
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 400:
            print("✅ TEST 4 PASSED: Correctly rejected invalid quantity")
        else:
            print("❌ TEST 4 FAILED: Should have rejected invalid quantity")
    
    print("\n" + "=" * 60)
    print("TESTS COMPLETED")
    print("=" * 60)

if __name__ == '__main__':
    test_product_transfer()
