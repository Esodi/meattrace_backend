"""
Script to delete all data from the database.
WARNING: This will delete ALL data including users, animals, products, etc.
Use with caution!
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from django.contrib.auth.models import User
from meat_trace.models import (
    UserProfile, Animal, SlaughterPart, Product, Order, OrderItem,
    CarcassMeasurement, Activity, JoinRequest, Shop, ProcessingUnit,
    ProcessingUnitUser, ShopUser, ProductIngredient, ProductCategory,
    ProcessingStage, ProductTimelineEvent, Inventory, Receipt, Notification,
    UserAuditLog
)

def delete_all_data():
    """Delete all data from all tables"""
    print("\n" + "="*80)
    print("⚠️  DATABASE CLEANUP - DELETING ALL DATA")
    print("="*80)
    
    # Count records before deletion
    models_to_clear = [
        ('Notifications', Notification),
        ('User Audit Logs', UserAuditLog),
        ('Order Items', OrderItem),
        ('Orders', Order),
        ('Receipts', Receipt),
        ('Inventory', Inventory),
        ('Product Timeline Events', ProductTimelineEvent),
        ('Product Ingredients', ProductIngredient),
        ('Products', Product),
        ('Processing Stages', ProcessingStage),
        ('Product Categories', ProductCategory),
        ('Slaughter Parts', SlaughterPart),
        ('Carcass Measurements', CarcassMeasurement),
        ('Animals', Animal),
        ('Activities', Activity),
        ('Join Requests', JoinRequest),
        ('Shop Users', ShopUser),
        ('Processing Unit Users', ProcessingUnitUser),
        ('Shops', Shop),
        ('Processing Units', ProcessingUnit),
        ('User Profiles', UserProfile),
        ('Users', User),
    ]
    
    print("\n📊 Current database state:")
    for name, model in models_to_clear:
        count = model.objects.count()
        print(f"   {name}: {count} records")
    
    # Confirm deletion
    print("\n⚠️  WARNING: This will permanently delete ALL data!")
    confirm = input("\nType 'DELETE ALL' to confirm: ")
    
    if confirm != 'DELETE ALL':
        print("\n❌ Deletion cancelled. Database unchanged.")
        return False
    
    print("\n🗑️  Deleting all data...")
    
    # Delete in order to respect foreign key constraints
    deleted_counts = {}
    for name, model in models_to_clear:
        count = model.objects.count()
        model.objects.all().delete()
        deleted_counts[name] = count
        print(f"   ✓ Deleted {count} {name}")
    
    print("\n✅ All data deleted successfully!")
    print("\n📊 Final database state:")
    for name, model in models_to_clear:
        count = model.objects.count()
        print(f"   {name}: {count} records")
    
    # Summary
    total_deleted = sum(deleted_counts.values())
    print(f"\n🎯 Total records deleted: {total_deleted}")
    
    return True


def main():
    try:
        success = delete_all_data()
        if success:
            print("\n✨ Database is now empty and ready for fresh data.")
            print("   You can now run migrations or create new test data.")
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == '__main__':
    main()
