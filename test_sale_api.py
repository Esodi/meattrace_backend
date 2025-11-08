import requests
import json

# Base URL
BASE_URL = "http://localhost:8000/api/v2"

# Login as shop user
login_data = {
    "username": "sss",
    "password": "ssssss"
}

print("Logging in...")
response = requests.post(f"{BASE_URL}/auth/login/", json=login_data)
print(f"Login status: {response.status_code}")

if response.status_code == 200:
    auth_data = response.json()
    print(f"Auth response: {json.dumps(auth_data, indent=2)}")
    token = auth_data.get('tokens', {}).get('access')
    if not token:
        print("No token found in response!")
        exit()
    print(f"Login successful! Token: {token[:20]}...")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Get products
    print("\nFetching products...")
    response = requests.get(f"{BASE_URL}/products/", headers=headers)
    print(f"Products status: {response.status_code}")
    
    if response.status_code == 200:
        products = response.json()
        print(f"Found {len(products)} products")
        if products:
            product = products[0]
            print(f"Using product: {product.get('name')} (ID: {product.get('id')})")
            
            # Create a sale
            sale_data = {
                "customer_name": "Test Customer",
                "customer_phone": "1234567890",
                "total_amount": "100.00",
                "payment_method": "cash",
                "items": [
                    {
                        "product": product.get('id'),
                        "quantity": "1.0",
                        "unit_price": "100.00"
                    }
                ]
            }
            
            print("\nCreating sale...")
            print(f"Sale data: {json.dumps(sale_data, indent=2)}")
            
            response = requests.post(f"{BASE_URL}/sales/", json=sale_data, headers=headers)
            print(f"Create sale status: {response.status_code}")
            print(f"Response: {response.text}")
            
            if response.status_code == 201:
                print("\n✓ Sale created successfully!")
            else:
                print(f"\n✗ Failed to create sale")
    else:
        print(f"Failed to fetch products: {response.text}")
else:
    print(f"Login failed: {response.text}")
