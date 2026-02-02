from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
import random
from meat_trace.models import (
    UserProfile, Animal, Product, SlaughterPart, 
    ProcessingUnit, ProcessingUnitUser, Shop, ShopUser, Inventory
)

class Command(BaseCommand):
    help = 'Seed the database with sample users and role-specific data'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting database seeding...'))

        # Password for all demo accounts
        password = 'demo123'

        # 1. Create Abattoir Users
        self.stdout.write('Creating Abattoir accounts...')
        abattoir_users = []
        for i in range(1, 3):
            username = f'abbatoir_{i}'
            email = f'abbatoir_{i}@example.com'
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(username=username, email=email, password=password)
                profile = user.profile
                profile.role = 'Abbatoir'
                profile.address = f'Abattoir Location {i}'
                profile.phone = f'+25570000000{i}'
                profile.save()
                abattoir_users.append(user)
                self.stdout.write(f'  - Created {username}')
            else:
                abattoir_users.append(User.objects.get(username=username))

        # 2. Create Processing Units and Processor Users
        self.stdout.write('Creating Processing Unit accounts...')
        for i in range(1, 3):
            unit_name = f'Demo Processing Unit {i}'
            username = f'processor_{i}'
            email = f'processor_{i}@example.com'
            
            unit, _ = ProcessingUnit.objects.get_or_create(
                name=unit_name,
                defaults={
                    'location': f'Processor Zone {i}',
                    'contact_phone': f'+25571111111{i}',
                    'license_number': f'PU-LIC-{i:03d}'
                }
            )
            
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(username=username, email=email, password=password)
                profile = user.profile
                profile.role = 'Processor'
                profile.processing_unit = unit
                profile.save()
                
                ProcessingUnitUser.objects.get_or_create(
                    user=user,
                    processing_unit=unit,
                    defaults={'role': 'owner', 'permissions': 'admin', 'joined_at': timezone.now()}
                )
                self.stdout.write(f'  - Created {username} (Owner of {unit_name})')

        # 3. Create Shops and Shop Owners
        self.stdout.write('Creating Shop accounts...')
        for i in range(1, 3):
            shop_name = f'Demo Shop {i}'
            username = f'shop_{i}'
            email = f'shop_{i}@example.com'
            
            shop, _ = Shop.objects.get_or_create(
                name=shop_name,
                defaults={
                    'location': f'Shop Street {i}',
                    'contact_phone': f'+25572222222{i}',
                    'business_license': f'SH-LIC-{i:03d}'
                }
            )
            
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(username=username, email=email, password=password)
                profile = user.profile
                profile.role = 'ShopOwner'
                profile.shop = shop
                profile.save()
                
                ShopUser.objects.get_or_create(
                    user=user,
                    shop=shop,
                    defaults={'role': 'owner', 'permissions': 'admin', 'joined_at': timezone.now()}
                )
                self.stdout.write(f'  - Created {username} (Owner of {shop_name})')

        # 4. Generate Sample Data for Abattoirs
        self.stdout.write('Generating sample Animals and Parts...')
        species_list = ['cow', 'pig', 'goat', 'sheep']
        for user in abattoir_users:
            for j in range(5):
                species = random.choice(species_list)
                animal = Animal.objects.create(
                    abbatoir=user,
                    species=species,
                    age=Decimal(str(random.randint(12, 48))),
                    live_weight=Decimal(str(random.randint(150, 450))),
                    gender=random.choice(['male', 'female']),
                    health_status='Healthy',
                    animal_name=f'Demo {species.capitalize()} {j+1}'
                )
                
                # Slaughter 3 out of 5
                if j < 3:
                    animal.slaughtered = True
                    animal.slaughtered_at = timezone.now()
                    animal.save()
                    
                    # Create some parts
                    SlaughterPart.objects.create(
                        animal=animal,
                        part_type='whole_carcass',
                        weight=animal.live_weight * Decimal('0.6'),
                        description='Seeded demo part'
                    )

        # 5. Generate Sample Products for Processing Units
        self.stdout.write('Generating sample Products for Processors...')
        processing_units = ProcessingUnit.objects.filter(name__startswith='Demo Processing Unit')
        for unit in processing_units:
            # Find an animal that was slaughtered (legacy demo animals or ours)
            animals = Animal.objects.filter(slaughtered=True)[:5]
            for animal in animals:
                Product.objects.create(
                    processing_unit=unit,
                    animal=animal,
                    name=f'Premium {animal.species.capitalize()} Cut',
                    product_type='meat',
                    quantity=Decimal('10'),
                    weight=Decimal('20.5'),
                    price=Decimal('15000'),
                    batch_number=f'DEMO-{unit.id}-{animal.id}'
                )

        # 6. Generate Inventory for Shops
        self.stdout.write('Generating sample Inventory for Shops...')
        shops = Shop.objects.filter(name__startswith='Demo Shop')
        products = Product.objects.all()[:10]
        for shop in shops:
            for product in random.sample(list(products), min(len(products), 5)):
                Inventory.objects.get_or_create(
                    shop=shop,
                    product=product,
                    defaults={'quantity': Decimal('50'), 'weight': Decimal('100.0')}
                )

        self.stdout.write(self.style.SUCCESS('\n✅ Database seeding completed!'))
        self.stdout.write(self.style.NOTICE('You can now log in with the created accounts using password: demo123'))
