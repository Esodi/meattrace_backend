"""
Test script to verify that farmers receive rejection notifications
when processing units reject animals or animal parts.

This test creates:
1. A farmer user
2. A processing unit user
3. An animal transferred from farmer to processing unit
4. Rejection of the animal by processing unit
5. Verification that farmer receives a notification

Run with: python test_rejection_notifications.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from django.contrib.auth.models import User
from meat_trace.models import Animal, ProcessingUnit, ProcessingUnitUser, Notification, UserProfile
from meat_trace.utils.rejection_service import RejectionService
from django.utils import timezone


def run_test():
    print("=" * 80)
    print("TESTING REJECTION NOTIFICATIONS")
    print("=" * 80)
    
    # Clean up test data
    print("\n1. Cleaning up existing test data...")
    User.objects.filter(username__in=['test_farmer_rejection', 'test_processor_rejection']).delete()
    ProcessingUnit.objects.filter(name='Test Processing Unit Rejection').delete()
    
    # Create farmer user
    print("\n2. Creating test farmer user...")
    farmer_user = User.objects.create_user(
        username='test_farmer_rejection',
        password='test123',
        email='farmer_rejection@test.com'
    )
    farmer_profile, _ = UserProfile.objects.get_or_create(
        user=farmer_user,
        defaults={'role': 'farmer'}
    )
    print(f"   ✓ Created farmer: {farmer_user.username}")
    
    # Create processing unit and processor user
    print("\n3. Creating test processing unit and processor user...")
    processing_unit = ProcessingUnit.objects.create(
        name='Test Processing Unit Rejection',
        address='123 Test St',
        city='Test City',
        state='Test State',
        zip_code='12345',
        country='Test Country'
    )
    
    processor_user = User.objects.create_user(
        username='test_processor_rejection',
        password='test123',
        email='processor_rejection@test.com'
    )
    processor_profile, _ = UserProfile.objects.get_or_create(
        user=processor_user,
        defaults={'role': 'processing_unit', 'processing_unit': processing_unit}
    )
    
    # Add processor to processing unit
    ProcessingUnitUser.objects.create(
        processing_unit=processing_unit,
        user=processor_user,
        role='admin',
        is_active=True,
        is_suspended=False
    )
    print(f"   ✓ Created processor: {processor_user.username}")
    print(f"   ✓ Created processing unit: {processing_unit.name}")
    
    # Create and transfer an animal
    print("\n4. Creating and transferring animal...")
    animal = Animal.objects.create(
        farmer=farmer_user,
        animal_id='TEST-REJECT-001',
        species='Cow',
        breed='Test Breed',
        date_of_birth=timezone.now().date(),
        live_weight=500.0
    )
    
    # Transfer to processing unit
    animal.transferred_to = processing_unit
    animal.transferred_at = timezone.now()
    animal.save()
    print(f"   ✓ Created and transferred animal: {animal.animal_id}")
    
    # Check notifications BEFORE rejection
    print("\n5. Checking farmer notifications BEFORE rejection...")
    notifications_before = Notification.objects.filter(user=farmer_user)
    print(f"   ℹ Farmer has {notifications_before.count()} notifications before rejection")
    
    # Reject the animal using RejectionService
    print("\n6. Rejecting animal using RejectionService...")
    rejection_data = {
        'category': 'quality_issue',
        'specific_reason': 'Animal does not meet quality standards',
        'notes': 'Weight below minimum requirement'
    }
    
    RejectionService.process_animal_rejection(
        animal=animal,
        rejection_data=rejection_data,
        rejected_by=processor_user,
        processing_unit=processing_unit
    )
    print(f"   ✓ Animal rejected by processor")
    
    # Verify animal rejection status
    animal.refresh_from_db()
    print(f"\n7. Verifying animal rejection status...")
    print(f"   - Rejection status: {animal.rejection_status}")
    print(f"   - Rejected by: {animal.rejected_by}")
    print(f"   - Rejection category: {animal.rejection_category}")
    print(f"   - Rejection reason: {animal.rejection_reason}")
    
    # Check notifications AFTER rejection
    print("\n8. Checking farmer notifications AFTER rejection...")
    notifications_after = Notification.objects.filter(user=farmer_user)
    new_notifications = notifications_after.count() - notifications_before.count()
    print(f"   ℹ Farmer has {notifications_after.count()} notifications after rejection")
    print(f"   ℹ New notifications: {new_notifications}")
    
    if new_notifications > 0:
        print("\n   ✅ SUCCESS! Farmer received notification(s)")
        print("\n   Notification details:")
        for notif in notifications_after.order_by('-created_at')[:new_notifications]:
            print(f"   - Type: {notif.notification_type}")
            print(f"   - Title: {notif.title}")
            print(f"   - Message: {notif.message}")
            print(f"   - Priority: {notif.priority}")
            print(f"   - Created: {notif.created_at}")
            print(f"   - Read: {notif.is_read}")
            print()
    else:
        print("\n   ❌ FAILED! Farmer did NOT receive any notifications")
        print("   This is the bug that was supposed to be fixed!")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    
    # Cleanup
    print("\n9. Cleaning up test data...")
    animal.delete()
    farmer_user.delete()
    processor_user.delete()
    processing_unit.delete()
    print("   ✓ Test data cleaned up")
    
    return new_notifications > 0


if __name__ == '__main__':
    success = run_test()
    exit(0 if success else 1)
