"""Test the processor API endpoint to verify animals are visible"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User

# Create a test client
client = Client()

# Login as processor (user ID 8, username 'bbb')
user = User.objects.get(id=8)
client.force_login(user)

print("=" * 80)
print(f"TESTING API ENDPOINT FOR PROCESSOR")
print("=" * 80)
print(f"User: {user.username} (ID: {user.id})")
print(f"Role: {user.profile.role}")
print(f"Processing Unit: {user.profile.processing_unit}")
print()

# Test the animals endpoint
print("GET /api/v2/animals/?ordering=-created_at&page_size=1000")
print("-" * 80)

response = client.get('/api/v2/animals/?ordering=-created_at&page_size=1000')

print(f"Status Code: {response.status_code}")
print(f"Content-Type: {response.get('Content-Type')}")
print()

if response.status_code == 200:
    import json
    data = response.json()
    
    if isinstance(data, list):
        print(f"Response is a list with {len(data)} animals")
        for i, animal in enumerate(data[:5]):
            print(f"\n  Animal {i+1}:")
            print(f"    ID: {animal.get('id')}")
            print(f"    animal_id: {animal.get('animal_id')}")
            print(f"    farmer_username: {animal.get('farmer_username')}")
            print(f"    transferred_to: {animal.get('transferred_to')}")
            print(f"    transferred_to_name: {animal.get('transferred_to_name')}")
            print(f"    received_by: {animal.get('received_by')}")
    elif isinstance(data, dict):
        results = data.get('results', [])
        print(f"Response is paginated with {len(results)} animals")
        print(f"Total count: {data.get('count')}")
        for i, animal in enumerate(results[:5]):
            print(f"\n  Animal {i+1}:")
            print(f"    ID: {animal.get('id')}")
            print(f"    animal_id: {animal.get('animal_id')}")
            print(f"    farmer_username: {animal.get('farmer_username')}")
            print(f"    transferred_to: {animal.get('transferred_to')}")
            print(f"    transferred_to_name: {animal.get('transferred_to_name')}")
            print(f"    received_by: {animal.get('received_by')}")
else:
    print(f"Error response: {response.content}")

print()
print("=" * 80)
