#!/usr/bin/env python
"""
Script to clear all data from the database while keeping admin users.
Run with: python clear_database.py
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.contrib.auth.models import User
from django.db import transaction
from meat_trace.models import (
    ProcessingUnit, ProcessingUnitUser, Shop, ShopUser, UserProfile,
    UserAuditLog, Animal, SlaughterPart, ProductIngredient, CarcassMeasurement,
    ProductCategory, ProcessingStage, ProductTimelineEvent, Product, Inventory,
    Receipt, Order, OrderItem, ComplianceAudit
)


def clear_all_data():
    print('Starting data cleanup...')

    with transaction.atomic():
        # Get admin users (superusers and staff)
        admin_users = User.objects.filter(is_superuser=True) | User.objects.filter(is_staff=True)
        admin_user_ids = list(admin_users.values_list('id', flat=True))
        
        print(f'Preserving {len(admin_user_ids)} admin user(s): {list(admin_users.values_list("username", flat=True))}')

        # Delete in order respecting foreign key constraints
        
        # Order-related
        count = OrderItem.objects.all().delete()[0]
        print(f'  Deleted {count} OrderItem(s)')
        
        count = Order.objects.all().delete()[0]
        print(f'  Deleted {count} Order(s)')

        # Inventory and receipts
        count = Receipt.objects.all().delete()[0]
        print(f'  Deleted {count} Receipt(s)')
        
        count = Inventory.objects.all().delete()[0]
        print(f'  Deleted {count} Inventory items')

        # Product-related
        count = ProductTimelineEvent.objects.all().delete()[0]
        print(f'  Deleted {count} ProductTimelineEvent(s)')
        
        count = ProductIngredient.objects.all().delete()[0]
        print(f'  Deleted {count} ProductIngredient(s)')
        
        count = Product.objects.all().delete()[0]
        print(f'  Deleted {count} Product(s)')
        
        count = ProductCategory.objects.all().delete()[0]
        print(f'  Deleted {count} ProductCategory(ies)')

        # Animal-related
        count = CarcassMeasurement.objects.all().delete()[0]
        print(f'  Deleted {count} CarcassMeasurement(s)')
        
        count = SlaughterPart.objects.all().delete()[0]
        print(f'  Deleted {count} SlaughterPart(s)')
        
        count = Animal.objects.all().delete()[0]
        print(f'  Deleted {count} Animal(s)')

        # Processing stages
        count = ProcessingStage.objects.all().delete()[0]
        print(f'  Deleted {count} ProcessingStage(s)')

        # Compliance
        count = ComplianceAudit.objects.all().delete()[0]
        print(f'  Deleted {count} ComplianceAudit(s)')

        # User associations and audit logs
        count = UserAuditLog.objects.all().delete()[0]
        print(f'  Deleted {count} UserAuditLog(s)')
        
        count = ProcessingUnitUser.objects.all().delete()[0]
        print(f'  Deleted {count} ProcessingUnitUser(s)')
        
        count = ShopUser.objects.all().delete()[0]
        print(f'  Deleted {count} ShopUser(s)')

        # Organizations
        count = Shop.objects.all().delete()[0]
        print(f'  Deleted {count} Shop(s)')
        
        count = ProcessingUnit.objects.all().delete()[0]
        print(f'  Deleted {count} ProcessingUnit(s)')

        # User profiles (except admin users)
        count = UserProfile.objects.exclude(user_id__in=admin_user_ids).delete()[0]
        print(f'  Deleted {count} UserProfile(s)')

        # Delete non-admin users
        count = User.objects.exclude(id__in=admin_user_ids).delete()[0]
        print(f'  Deleted {count} non-admin User(s)')

    print('\n✅ Data cleanup completed successfully!')
    print(f'Remaining admin users: {list(admin_users.values_list("username", flat=True))}')


if __name__ == '__main__':
    confirm = input('This will DELETE ALL DATA except admin users. Type "yes" to confirm: ')
    if confirm.lower() == 'yes':
        clear_all_data()
    else:
        print('Aborted.')
