import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from meat_trace.models import Animal

animals = Animal.objects.all()
print(f'Total animals: {animals.count()}')
print('\nStatus breakdown:')

status_counts = {
    'HEALTHY': 0,
    'SLAUGHTERED': 0,
    'TRANSFERRED': 0,
    'SEMI-TRANSFERRED': 0
}

for animal in animals[:20]:  # Check first 20 animals
    status = animal.lifecycle_status
    status_counts[status] += 1
    print(f'  {animal.animal_id}: slaughtered={animal.slaughtered}, transferred_to={animal.transferred_to}, parts={animal.slaughter_parts.count()}, status={status}')

print('\nStatus Summary:')
for status, count in status_counts.items():
    print(f'  {status}: {count}')

# Check if any animals have transfers
transferred_animals = Animal.objects.filter(transferred_to__isnull=False)
print(f'\nAnimals with transferred_to set: {transferred_animals.count()}')

# Check if any animals have slaughter parts
animals_with_parts = Animal.objects.filter(slaughter_parts__isnull=False).distinct()
print(f'Animals with slaughter parts: {animals_with_parts.count()}')