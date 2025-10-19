#!/usr/bin/env python
"""Test script to verify animals API returns unpaginated data."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from django.contrib.auth.models import User
from meat_trace.models import Animal
from meat_trace.serializers import AnimalSerializer
from rest_framework.test import APIRequestFactory, force_authenticate
from meat_trace.views import AnimalViewSet

# Get a test user
user = User.objects.get(username='aaa')

# Create a request
factory = APIRequestFactory()
request = factory.get('/api/v2/animals/')
force_authenticate(request, user=user)

# Create viewset and call list
view = AnimalViewSet.as_view({'get': 'list'})
response = view(request)

print("\n" + "="*60)
print("🧪 ANIMAL API TEST RESULTS")
print("="*60)
print(f"✅ Response status: {response.status_code}")
print(f"📊 Response data type: {type(response.data)}")
print(f"📦 Is List?: {isinstance(response.data, list)}")
print(f"📦 Is Dict?: {isinstance(response.data, dict)}")

if isinstance(response.data, list):
    print(f"✅ SUCCESS! Response is a direct list (unpaginated)")
    print(f"📋 Total animals: {len(response.data)}")
    if response.data:
        print(f"\n📝 First animal sample:")
        first = response.data[0]
        print(f"   - ID: {first.get('id')}")
        print(f"   - Animal ID: {first.get('animal_id')}")
        print(f"   - Species: {first.get('species')}")
        print(f"   - Slaughtered: {first.get('slaughtered')}")
        print(f"   - Farmer: {first.get('farmer_username')}")
elif isinstance(response.data, dict):
    print(f"⚠️  Response is a dict (might be paginated)")
    print(f"   Keys: {response.data.keys()}")
    if 'results' in response.data:
        print(f"❌ PAGINATED! Has 'results' key")
        print(f"   Total: {len(response.data['results'])}")
    else:
        print(f"   No 'results' key found")

# Also test the queryset directly
print("\n" + "="*60)
print("🔍 DATABASE QUERY TEST")
print("="*60)
animals = Animal.objects.filter(farmer=user)
print(f"📊 Total animals for user '{user.username}': {animals.count()}")
print(f"📊 Non-slaughtered: {animals.filter(slaughtered=False).count()}")
print(f"📊 Slaughtered: {animals.filter(slaughtered=True).count()}")

non_slaughtered = animals.filter(slaughtered=False)
if non_slaughtered.exists():
    print(f"\n📝 Non-slaughtered animals:")
    for animal in non_slaughtered[:5]:
        print(f"   - {animal.animal_id}: {animal.species} (ID: {animal.id})")

print("="*60)
print("✅ Test complete!")
print("="*60 + "\n")
