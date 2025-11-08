"""Initialize remaining_weight for existing animals and slaughter parts"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from meat_trace.models import Animal, SlaughterPart

# Update animals
animals = Animal.objects.filter(remaining_weight__isnull=True)
animals_count = animals.count()
print(f"Found {animals_count} animals without remaining_weight")

for animal in animals:
    animal.remaining_weight = animal.live_weight or 0
    animal.save()
print(f"✅ Updated {animals_count} animals")

# Update slaughter parts
parts = SlaughterPart.objects.filter(remaining_weight__isnull=True)
parts_count = parts.count()
print(f"Found {parts_count} slaughter parts without remaining_weight")

for part in parts:
    part.remaining_weight = part.weight
    part.save()
print(f"✅ Updated {parts_count} slaughter parts")

print(f"\n🎉 Total: Updated {animals_count} animals and {parts_count} slaughter parts")
