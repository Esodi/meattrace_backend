import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from meat_trace.models import Animal, User
from django.contrib.auth.models import User as AuthUser

print("=== Debugging Animal Registration Issue ===\n")

# Get all users
users = User.objects.all()
print(f"Total users: {users.count()}")
for user in users:
    if hasattr(user, 'profile'):
        print(f"  - {user.username} (ID: {user.id}, Role: {user.profile.role})")
    else:
        print(f"  - {user.username} (ID: {user.id}, No profile)")

print("\n=== All Animals ===")
animals = Animal.objects.all().order_by('-created_at')
print(f"Total animals: {animals.count()}\n")

for animal in animals[:10]:  # Show last 10
    print(f"Animal ID: {animal.id}")
    print(f"  animal_id: {animal.animal_id}")
    print(f"  animal_name: {animal.animal_name}")
    print(f"  species: {animal.species}")
    print(f"  farmer: {animal.farmer.username} (ID: {animal.farmer.id})")
    print(f"  created_at: {animal.created_at}")
    print(f"  slaughtered: {animal.slaughtered}")
    print(f"  transferred_to: {animal.transferred_to}")
    print()

print("\n=== Recent Animals (Last 5) ===")
recent = Animal.objects.all().order_by('-created_at')[:5]
for animal in recent:
    print(f"{animal.animal_id} - {animal.species} - Farmer: {animal.farmer.username}")
