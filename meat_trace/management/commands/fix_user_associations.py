from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from meat_trace.models import UserProfile, ProcessingUnit, ProcessingUnitUser, Shop, ShopUser


class Command(BaseCommand):
    help = 'Fix all users with ProcessingUnit or Shop roles who are missing their associations'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting user association fix...'))
        
        # Fix ProcessingUnit users
        self.stdout.write('\n=== Fixing ProcessingUnit Users ===')
        processing_unit_profiles = UserProfile.objects.filter(role='ProcessingUnit')
        fixed_pu_count = 0
        
        for profile in processing_unit_profiles:
            user = profile.user
            
            if not profile.processing_unit:
                self.stdout.write(f'User {user.username} has role ProcessingUnit but no processing_unit')
                
                # Try to find active membership
                active_membership = ProcessingUnitUser.objects.filter(
                    user=user,
                    is_active=True
                ).select_related('processing_unit').first()
                
                if active_membership:
                    # Link existing membership
                    profile.processing_unit = active_membership.processing_unit
                    profile.save()
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✓ Linked {user.username} to existing processing unit: {active_membership.processing_unit.name}'
                    ))
                    fixed_pu_count += 1
                else:
                    # Create new processing unit and membership
                    processing_unit = ProcessingUnit.objects.create(
                        name=f"{user.username}'s Processing Unit",
                        description=f"Auto-created processing unit for {user.username}",
                        contact_email=user.email
                    )
                    
                    ProcessingUnitUser.objects.create(
                        user=user,
                        processing_unit=processing_unit,
                        role='owner',
                        permissions='admin',
                        invited_by=user,
                        invited_at=timezone.now(),
                        joined_at=timezone.now(),
                        is_active=True
                    )
                    
                    profile.processing_unit = processing_unit
                    profile.save()
                    
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✓ Created processing unit "{processing_unit.name}" for {user.username}'
                    ))
                    fixed_pu_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'\nFixed {fixed_pu_count} ProcessingUnit users'))
        
        # Fix Shop users
        self.stdout.write('\n=== Fixing Shop Users ===')
        shop_profiles = UserProfile.objects.filter(role='Shop')
        fixed_shop_count = 0
        
        for profile in shop_profiles:
            user = profile.user
            
            if not profile.shop:
                self.stdout.write(f'User {user.username} has role Shop but no shop')
                
                # Try to find active membership
                active_membership = ShopUser.objects.filter(
                    user=user,
                    is_active=True
                ).select_related('shop').first()
                
                if active_membership:
                    # Link existing membership
                    profile.shop = active_membership.shop
                    profile.save()
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✓ Linked {user.username} to existing shop: {active_membership.shop.name}'
                    ))
                    fixed_shop_count += 1
                else:
                    # Create new shop and membership
                    shop = Shop.objects.create(
                        name=f"{user.username}'s Shop",
                        description=f"Auto-created shop for {user.username}",
                        contact_email=user.email,
                        is_active=True
                    )
                    
                    ShopUser.objects.create(
                        user=user,
                        shop=shop,
                        role='owner',
                        permissions='admin',
                        invited_by=user,
                        invited_at=timezone.now(),
                        joined_at=timezone.now(),
                        is_active=True
                    )
                    
                    profile.shop = shop
                    profile.save()
                    
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✓ Created shop "{shop.name}" for {user.username}'
                    ))
                    fixed_shop_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'\nFixed {fixed_shop_count} Shop users'))
        
        # Summary
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(self.style.SUCCESS(f'Total users fixed: {fixed_pu_count + fixed_shop_count}'))
        self.stdout.write(self.style.SUCCESS('All user associations have been fixed!'))
