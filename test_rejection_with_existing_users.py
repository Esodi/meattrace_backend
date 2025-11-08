"""
Test rejection notifications with existing users.

Farmer: aaa / aaaaaa
Processing Unit: bbb / bbbbbb

This script will:
1. Authenticate both users
2. Create an animal as farmer
3. Transfer it to processing unit
4. Reject it as processing unit
5. Check if farmer received notification
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from django.contrib.auth.models import User
from meat_trace.models import Animal, ProcessingUnit, ProcessingUnitUser, Notification
from meat_trace.utils.rejection_service import RejectionService
from django.utils import timezone


def run_test():
    print("=" * 80)
    print("TESTING REJECTION NOTIFICATIONS WITH EXISTING USERS")
    print("=" * 80)
    
    # Get existing users
    print("\n1. Loading existing users...")
    try:
        farmer_user = User.objects.get(username='aaa')
        print(f"   ✓ Found farmer: {farmer_user.username}")
    except User.DoesNotExist:
        print("   ❌ Farmer user 'aaa' not found!")
        return False
    
    try:
        processor_user = User.objects.get(username='bbb')
        print(f"   ✓ Found processor: {processor_user.username}")
    except User.DoesNotExist:
        print("   ❌ Processor user 'bbb' not found!")
        return False
    
    # Get processing unit for processor
    print("\n2. Getting processing unit...")
    try:
        pu_user = ProcessingUnitUser.objects.filter(
            user=processor_user,
            is_active=True,
            is_suspended=False
        ).first()
        
        if not pu_user:
            print("   ❌ No processing unit found for user 'bbb'!")
            return False
        
        processing_unit = pu_user.processing_unit
        print(f"   ✓ Found processing unit: {processing_unit.name}")
    except Exception as e:
        print(f"   ❌ Error getting processing unit: {e}")
        return False
    
    # Create and transfer an animal
    print("\n3. Creating and transferring test animal...")
    animal = Animal.objects.create(
        farmer=farmer_user,
        animal_id=f'TEST-NOTIF-{timezone.now().strftime("%Y%m%d%H%M%S")}',
        species='cow',
        breed='Test Breed',
        age=24,  # 24 months (2 years)
        live_weight=450.0
    )
    
    # Transfer to processing unit
    animal.transferred_to = processing_unit
    animal.transferred_at = timezone.now()
    animal.save()
    print(f"   ✓ Created and transferred animal: {animal.animal_id}")
    
    # Count farmer notifications BEFORE rejection
    print("\n4. Checking farmer notifications BEFORE rejection...")
    notifications_before = Notification.objects.filter(user=farmer_user).count()
    print(f"   ℹ Farmer has {notifications_before} notifications")
    
    # Reject the animal
    print("\n5. Processing unit rejecting the animal...")
    rejection_data = {
        'category': 'quality_issue',
        'specific_reason': 'Does not meet quality standards',
        'notes': 'Test rejection for notification verification'
    }
    
    try:
        RejectionService.process_animal_rejection(
            animal=animal,
            rejection_data=rejection_data,
            rejected_by=processor_user,
            processing_unit=processing_unit
        )
        print(f"   ✓ Animal rejected successfully")
    except Exception as e:
        print(f"   ❌ Error rejecting animal: {e}")
        return False
    
    # Verify rejection
    animal.refresh_from_db()
    print(f"\n6. Verifying rejection status...")
    print(f"   - Status: {animal.rejection_status}")
    print(f"   - Category: {animal.rejection_reason_category}")
    print(f"   - Reason: {animal.rejection_reason_specific}")
    print(f"   - Rejected by: {animal.rejected_by}")
    
    # Count farmer notifications AFTER rejection
    print("\n7. Checking farmer notifications AFTER rejection...")
    notifications_after = Notification.objects.filter(user=farmer_user).count()
    new_notifications = notifications_after - notifications_before
    print(f"   ℹ Farmer has {notifications_after} notifications")
    print(f"   ℹ NEW notifications: {new_notifications}")
    
    if new_notifications > 0:
        print("\n   ✅ SUCCESS! Farmer received notification(s)!")
        print("\n   Latest notification details:")
        latest_notif = Notification.objects.filter(user=farmer_user).order_by('-created_at').first()
        if latest_notif:
            print(f"   - Type: {latest_notif.notification_type}")
            print(f"   - Title: {latest_notif.title}")
            print(f"   - Message: {latest_notif.message}")
            print(f"   - Priority: {latest_notif.priority}")
            print(f"   - Created: {latest_notif.created_at}")
            print(f"   - Is Read: {latest_notif.is_read}")
    else:
        print("\n   ❌ FAILED! Farmer did NOT receive notification!")
        print("   The bug still exists!")
    
    print("\n" + "=" * 80)
    print("TEST RESULT:", "✅ PASSED" if new_notifications > 0 else "❌ FAILED")
    print("=" * 80)
    
    # Ask if we should clean up
    print(f"\n8. Test animal '{animal.animal_id}' was created for this test.")
    print("   You can manually delete it later if needed.")
    
    return new_notifications > 0


if __name__ == '__main__':
    success = run_test()
    exit(0 if success else 1)
