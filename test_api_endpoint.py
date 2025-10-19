import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from meat_trace.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

# Get user
u = User.objects.get(username='nedp')
print(f"Testing with user: {u.username}")
print(f"User profile role: {u.profile.role}")
print(f"User profile processing_unit: {u.profile.processing_unit}")

# Generate token
token = str(RefreshToken.for_user(u).access_token)
print(f"\nToken generated: {token[:50]}...")

# Create API client
client = APIClient()
client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

# Test the endpoint
print("\n" + "="*80)
print("Testing GET /api/v2/animals/transferred_animals/")
print("="*80)

response = client.get('/api/v2/animals/transferred_animals/')
print(f"\nStatus Code: {response.status_code}")
print(f"Content Type: {response.get('Content-Type', 'Not specified')}")

if hasattr(response, 'data'):
    print(f"\nResponse Data:")
    import json
    print(json.dumps(response.data, indent=2))
else:
    print(f"\nRaw Content:")
    print(response.content.decode())
