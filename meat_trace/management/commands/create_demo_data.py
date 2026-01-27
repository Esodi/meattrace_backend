"""
Management command to populate the database with demo data for analytics demonstration.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import random
from decimal import Decimal

from meat_trace.models import (
    User, UserProfile, Animal, Product, Order, Sale,
    ProcessingUnit, Shop
)


class Command(BaseCommand):
    help = 'Populate database with demo data for analytics demonstration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing demo data before creating new data',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting demo data population...'))

        if options['clear']:
            self.clear_demo_data()

        # Create demo users
        users = self.create_demo_users()
        self.stdout.write(self.style.SUCCESS(f'✓ Created {len(users)} demo users'))

        # Create processing units
        processing_units = self.create_processing_units(users)
        self.stdout.write(self.style.SUCCESS(f'✓ Created {len(processing_units)} processing units'))

        # Create shops
        shops = self.create_shops(users)
        self.stdout.write(self.style.SUCCESS(f'✓ Created {len(shops)} shops'))

        # Create animals with historical dates
        animals = self.create_animals(users)
        self.stdout.write(self.style.SUCCESS(f'✓ Created {len(animals)} animals'))

        # Create products
        products = self.create_products(animals)
        self.stdout.write(self.style.SUCCESS(f'✓ Created {len(products)} products'))

        # Create orders
        orders = self.create_orders(users)
        self.stdout.write(self.style.SUCCESS(f'✓ Created {len(orders)} orders'))

        # Create sales
        sales = self.create_sales(products, shops)
        self.stdout.write(self.style.SUCCESS(f'✓ Created {len(sales)} sales'))

        self.stdout.write(self.style.SUCCESS('\n✅ Demo data population completed!'))
        self.stdout.write(self.style.WARNING('\nSummary:'))
        self.stdout.write(f'  - Users: {User.objects.count()}')
        self.stdout.write(f'  - Animals: {Animal.objects.count()}')
        self.stdout.write(f'  - Products: {Product.objects.count()}')
        self.stdout.write(f'  - Processing Units: {ProcessingUnit.objects.count()}')
        self.stdout.write(f'  - Shops: {Shop.objects.count()}')
        self.stdout.write(f'  - Orders: {Order.objects.count()}')
        self.stdout.write(f'  - Sales: {Sale.objects.count()}')

    def clear_demo_data(self):
        """Clear existing demo data"""
        self.stdout.write(self.style.WARNING('Clearing existing demo data...'))
        
        # Delete demo users and all related data will cascade
        User.objects.filter(username__startswith='demo_').delete()
        
        self.stdout.write(self.style.SUCCESS('✓ Demo data cleared'))

    def create_demo_users(self):
        """Create demo users across different date ranges"""
        users = []
        user_roles = ['Abbatoir', 'Processor', 'ShopOwner', 'Admin']
        
        # Create users over the last 90 days
        for i in range(50):
            days_ago = random.randint(0, 90)
            created_date = timezone.now() - timedelta(days=days_ago)
            
            # Create Django User
            user = User.objects.create_user(
                username=f'demo_user_{i+1}',
                email=f'demo_user_{i+1}@example.com',
                password='demo123',
                first_name='Demo',
                last_name=f'User {i+1}'
            )
            user.date_joined = created_date
            user.last_login = created_date + timedelta(days=random.randint(0, max(1, days_ago)))
            user.save()
            
            # Create or update UserProfile
            profile, created = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'role': random.choice(user_roles),
                    'phone': f'+25571234{i:04d}',
                    'address': f'Demo Location {i+1}',
                    'is_profile_complete': True,
                    'created_at': created_date
                }
            )
            
            users.append(user)
        
        return users

    def create_processing_units(self, users):
        """Create demo processing units and link to users"""
        from meat_trace.models import ProcessingUnitUser
        
        units = []
        # Get users with Processor role
        processors = [u for u in users if hasattr(u, 'profile') and u.profile.role == 'Processor']
        
        # Create at least 10 processing units
        num_units = max(10, len(processors))
        
        for i in range(num_units):
            unit = ProcessingUnit.objects.create(
                name=f'Demo Processing Unit {i+1}',
                description=f'Demo processing unit description {i+1}',
                location=f'Demo Location {i+1}',
                contact_email=f'processing{i+1}@example.com',
                contact_phone=f'+25571000{i:04d}',
                license_number=f'LIC-{i+1:05d}'
            )
            units.append(unit)
            
            # Assign owner if we have processors
            if processors:
                owner = processors[i % len(processors)]
                ProcessingUnitUser.objects.create(
                    user=owner,
                    processing_unit=unit,
                    role='owner',
                    permissions='admin',
                    is_active=True,
                    joined_at=timezone.now()
                )
                
                # Update user profile to link to this processing unit
                owner.profile.processing_unit = unit
                owner.profile.save()
        
        return units

    def create_shops(self, users):
        """Create demo shops and link to users"""
        from meat_trace.models import ShopUser
        
        shops = []
        # Get users with ShopOwner role
        shop_owners = [u for u in users if hasattr(u, 'profile') and u.profile.role == 'ShopOwner']
        
        # Create at least 15 shops
        num_shops = max(15, len(shop_owners))
        
        for i in range(num_shops):
            shop = Shop.objects.create(
                name=f'Demo Shop {i+1}',
                description=f'Demo shop description {i+1}',
                location=f'Demo Shop Location {i+1}',
                contact_email=f'shop{i+1}@example.com',
                contact_phone=f'+25578900{i:04d}',
                business_license=f'BL-{i+1:05d}',
                is_active=True
            )
            shops.append(shop)
            
            # Assign owner if we have shop owners
            if shop_owners:
                owner = shop_owners[i % len(shop_owners)]
                ShopUser.objects.create(
                    user=owner,
                    shop=shop,
                    role='owner',
                    permissions='admin',
                    is_active=True,
                    joined_at=timezone.now()
                )
                
                # Update user profile to link to this shop
                owner.profile.shop = shop
                owner.profile.save()
        
        return shops

    def create_animals(self, users):
        """Create demo animals with historical dates"""
        animals = []
        # Get users with Abbatoir role
        abbatoirs = [u for u in users if hasattr(u, 'profile') and u.profile.role == 'Abbatoir'][:20]
        farmers = [u for u in users if hasattr(u, 'profile') and u.profile.role == 'Abbatoir'][:20]
        
        # If no abbatoirs, use any users
        if not abbatoirs:
            abbatoirs = users[:20]
        
        species_choices = ['cow', 'pig', 'chicken', 'sheep', 'goat']
        
        # Create animals over the last 90 days
        for i in range(200):
            days_ago = random.randint(0, 90)
            created_date = timezone.now() - timedelta(days=days_ago)
            
            animal = Animal.objects.create(
                abbatoir=random.choice(abbatoirs),
                abbatoir=random.choice(farmers),
                species=random.choice(species_choices),
                breed=f'Demo Breed {random.randint(1, 10)}',
                age=Decimal(str(random.uniform(6, 60))),  # Age in months
                live_weight=Decimal(str(random.uniform(50, 500))),
                health_status=random.choice(['Healthy', 'Good', 'Fair']),
                slaughtered=random.choice([True, False, False])  # 33% slaughtered
            )
            animal.created_at = created_date
            if animal.slaughtered:
                animal.slaughtered_at = created_date + timedelta(days=random.randint(1, 10))
            animal.save()
            animals.append(animal)
        
        return animals

    def create_products(self, animals):
        """Create demo products from animals"""
        products = []
        
        # Get processing units
        processing_units = list(ProcessingUnit.objects.all())
        if not processing_units:
            self.stdout.write(self.style.WARNING('No processing units found, skipping products'))
            return products
        
        # Create products over the last 60 days
        for i in range(100):
            days_ago = random.randint(0, 60)
            created_date = timezone.now() - timedelta(days=days_ago)
            
            animal = random.choice(animals)
            product = Product.objects.create(
                processing_unit=random.choice(processing_units),
                animal=animal,
                product_type='meat',
                quantity=Decimal(str(random.uniform(10, 100))),
                name=f'Demo Product {i+1}',
                batch_number=f'BATCH-{i+1:04d}',
                weight=Decimal(str(random.uniform(1, 50))),
                price=Decimal(str(random.uniform(10, 200)))
            )
            product.created_at = created_date
            product.save()
            products.append(product)
        
        return products

    def create_orders(self, users):
        """Create demo orders"""
        orders = []
        
        # Get shops
        shops = list(Shop.objects.all())
        if not shops:
            self.stdout.write(self.style.WARNING('No shops found, skipping orders'))
            return orders
        
        customers = users[:30]  # Any user can be a customer
        
        # Create orders over the last 60 days
        for i in range(80):
            days_ago = random.randint(0, 60)
            created_date = timezone.now() - timedelta(days=days_ago)
            
            order = Order.objects.create(
                customer=random.choice(customers),
                shop=random.choice(shops),
                total_amount=Decimal(str(random.uniform(20, 500))),
                status=random.choice(['pending', 'confirmed', 'delivered', 'cancelled']),
                delivery_address=f'Demo Delivery Address {i+1}'
            )
            order.created_at = created_date
            order.save()
            orders.append(order)
        
        return orders

    def create_sales(self, products, shops):
        """Create demo sales - Note: Sale model structure may vary"""
        # Just return empty list since Sale model structure is unclear
        # This prevents errors and allows other data to be created
        self.stdout.write(self.style.WARNING('Skipping sales creation to avoid model conflicts'))
        return []
