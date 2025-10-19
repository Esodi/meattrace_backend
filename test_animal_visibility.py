import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from meat_trace.models import Animal, User
from django.utils import timezone
from datetime import timedelta

print("=== Testing Animal Registration and Retrieval ===\n")

# Get the farmer user
try:
    farmer = User.objects.get(username='aaa')
    print(f"Found farmer: {farmer.username} (ID: {farmer.id})")
    print(f"  Role: {farmer.profile.role}\n")
except User.DoesNotExist:
    print("ERROR: User 'aaa' not found!")
    exit(1)

# Check recent animals for this farmer
print("=== Animals for this farmer ===")
farmer_animals = Animal.objects.filter(farmer=farmer).order_by('-created_at')
print(f"Total animals: {farmer_animals.count()}\n")

# Show last 5
for animal in farmer_animals[:5]:
    print(f"Animal: {animal.animal_id}")
    print(f"  Name: {animal.animal_name}")
    print(f"  Species: {animal.species}")
    print(f"  Created: {animal.created_at}")
    print(f"  Slaughtered: {animal.slaughtered}")
    print(f"  Age (seconds): {(timezone.now() - animal.created_at).total_seconds()}")
    print()

# Simulate API call - what would the farmer see?
print("\n=== Simulating API GET /api/v2/animals/ (farmer's view) ===")
api_animals = Animal.objects.filter(farmer=farmer).order_by('-created_at')
print(f"API would return {api_animals.count()} animals")
for animal in api_animals[:5]:
    print(f"  - {animal.animal_id} ({animal.species}) - Created: {animal.created_at}")
