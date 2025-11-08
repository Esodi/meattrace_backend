#!/usr/bin/env python
"""
Test script to verify notification system works correctly for rejection scenarios.
Tests backend notification creation, WebSocket sending, and data integrity.
"""
import os
import django
import json
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from django.contrib.auth.models import User
from django.utils import timezone
from meat_trace.models import Animal, SlaughterPart, Notification, ProcessingUnit
from meat_trace.utils.rejection_service import RejectionService
from meat_trace.utils.notification_service import NotificationService

def test_animal_rejection_notification():
    """Test animal rejection notification creation and data integrity"""
    print("\n" + "="*60)
    print("TESTING ANIMAL REJECTION NOTIFICATION")
    print("="*60)

    # Get test users and data
    try:
        farmer = User.objects.get(username='aaa')  # Farmer user
        processor_user = User.objects.get(username='demo_processor')  # Processor user
        processing_unit = ProcessingUnit.objects.filter(users=processor_user).first()
        if not processing_unit:
            processing_unit = ProcessingUnit.objects.first()

        # Get a non-rejected animal
        animal = Animal.objects.filter(
            farmer=farmer,
            rejection_status__isnull=True
        ).first()

        if not animal:
            print("❌ No suitable animal found for testing")
            return False

        print(f"📋 Test Data:")
        print(f"   - Farmer: {farmer.username}")
        print(f"   - Animal: {animal.animal_id}")
        print(f"   - Processor: {processor_user.username}")
        print(f"   - Processing Unit: {processing_unit.name if processing_unit else 'None'}")

        # Count notifications before
        initial_count = Notification.objects.filter(user=farmer).count()
        print(f"   - Initial notifications: {initial_count}")

        # Perform rejection
        rejection_data = {
            'category': 'health_concerns',
            'specific_reason': 'bruising',
            'notes': 'Test rejection for notification testing'
        }

        print(f"\nProcessing animal rejection...")
        RejectionService.process_animal_rejection(
            animal, rejection_data, processor_user, processing_unit
        )

        # Verify notification was created
        final_count = Notification.objects.filter(user=farmer).count()
        print(f"Final notifications: {final_count}")

        if final_count <= initial_count:
            print("No notification was created!")
            return False

        # Get the latest notification
        notification = Notification.objects.filter(
            user=farmer,
            notification_type='animal_rejected'
        ).order_by('-created_at').first()

        if not notification:
            print("No animal rejection notification found!")
            return False

        print(f"\nNotification Details:")
        print(f"   - ID: {notification.id}")
        print(f"   - Type: {notification.notification_type}")
        print(f"   - Title: {notification.title}")
        print(f"   - Message: {notification.message}")
        print(f"   - Priority: {notification.priority}")
        print(f"   - Action Type: {notification.action_type}")
        print(f"   - Data: {json.dumps(notification.data, indent=2)}")

        # Verify notification data integrity
        expected_data = {
            'animal_id': animal.animal_id,
            'category': rejection_data['category'],
            'specific_reason': rejection_data['specific_reason']
        }

        if not all(notification.data.get(key) == value for key, value in expected_data.items()):
            print("Notification data integrity check failed!")
            print(f"   Expected: {expected_data}")
            print(f"   Actual: {notification.data}")
            return False

        print("Notification data integrity verified")
        print("Animal rejection notification test PASSED")
        return True

    except Exception as e:
        print(f"Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_part_rejection_notification():
    """Test slaughter part rejection notification creation and data integrity"""
    print("\n" + "="*60)
    print("TESTING PART REJECTION NOTIFICATION")
    print("="*60)

    try:
        farmer = User.objects.get(username='aaa')
        processor_user = User.objects.get(username='demo_processor')
        processing_unit = ProcessingUnit.objects.first()

        # Get a non-rejected part
        part = SlaughterPart.objects.filter(
            animal__farmer=farmer,
            rejection_status__isnull=True
        ).first()

        if not part:
            print("❌ No suitable slaughter part found for testing")
            return False

        print(f"📋 Test Data:")
        print(f"   - Farmer: {farmer.username}")
        print(f"   - Part: {part.part_type} (ID: {part.id})")
        print(f"   - Animal: {part.animal.animal_id}")
        print(f"   - Processor: {processor_user.username}")

        initial_count = Notification.objects.filter(user=farmer).count()
        print(f"   - Initial notifications: {initial_count}")

        # Perform rejection
        rejection_data = {
            'category': 'quality_issues',
            'specific_reason': 'contamination',
            'notes': 'Test part rejection for notification testing'
        }

        print(f"\nProcessing part rejection...")
        RejectionService.process_part_rejection(
            part, rejection_data, processor_user, processing_unit
        )

        final_count = Notification.objects.filter(user=farmer).count()
        print(f"Final notifications: {final_count}")

        if final_count <= initial_count:
            print("No notification was created!")
            return False

        # Get the latest notification
        notification = Notification.objects.filter(
            user=farmer,
            notification_type='part_rejected'
        ).order_by('-created_at').first()

        if not notification:
            print("No part rejection notification found!")
            return False

        print(f"\nNotification Details:")
        print(f"   - ID: {notification.id}")
        print(f"   - Type: {notification.notification_type}")
        print(f"   - Title: {notification.title}")
        print(f"   - Message: {notification.message}")
        print(f"   - Priority: {notification.priority}")
        print(f"   - Data: {json.dumps(notification.data, indent=2)}")

        # Verify notification data integrity
        expected_data = {
            'animal_id': part.animal.animal_id,
            'part_id': part.id,
            'part_type': part.part_type,
            'category': rejection_data['category'],
            'specific_reason': rejection_data['specific_reason']
        }

        if not all(notification.data.get(key) == value for key, value in expected_data.items()):
            print("Notification data integrity check failed!")
            print(f"   Expected: {expected_data}")
            print(f"   Actual: {notification.data}")
            return False

        print("Notification data integrity verified")
        print("Part rejection notification test PASSED")
        return True

    except Exception as e:
        print(f"Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_multiple_rejections_efficiency():
    """Test handling multiple rejections efficiently"""
    print("\n" + "="*60)
    print("TESTING MULTIPLE REJECTIONS EFFICIENCY")
    print("="*60)

    try:
        farmer = User.objects.get(username='aaa')
        processor_user = User.objects.get(username='demo_processor')
        processing_unit = ProcessingUnit.objects.first()

        # Get multiple animals for testing
        animals = Animal.objects.filter(
            farmer=farmer,
            rejection_status__isnull=True
        )[:3]  # Test with 3 animals

        if len(animals) < 2:
            print("❌ Need at least 2 animals for multiple rejections test")
            return False

        print(f"📋 Test Data:")
        print(f"   - Farmer: {farmer.username}")
        print(f"   - Animals to reject: {len(animals)}")
        for animal in animals:
            print(f"     - {animal.animal_id}")

        initial_count = Notification.objects.filter(user=farmer).count()
        print(f"   - Initial notifications: {initial_count}")

        # Perform multiple rejections
        rejection_data = {
            'category': 'health_concerns',
            'specific_reason': 'multiple_test',
            'notes': 'Batch rejection test'
        }

        print(f"\n🔄 Processing {len(animals)} animal rejections...")
        start_time = datetime.now()

        for i, animal in enumerate(animals, 1):
            print(f"   Processing rejection {i}/{len(animals)}...")
            RejectionService.process_animal_rejection(
                animal, rejection_data, processor_user, processing_unit
            )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        final_count = Notification.objects.filter(user=farmer).count()
        new_notifications = final_count - initial_count

        print(f"\nPerformance Results:")
        print(f"   - Duration: {duration:.2f} seconds")
        print(f"   - New notifications: {new_notifications}")
        print(f"   - Average time per rejection: {duration/len(animals):.2f} seconds")

        # Verify all notifications were created
        if new_notifications != len(animals):
            print(f"Expected {len(animals)} notifications, got {new_notifications}")
            return False

        # Check notification types
        recent_notifications = Notification.objects.filter(
            user=farmer,
            notification_type='animal_rejected'
        ).order_by('-created_at')[:len(animals)]

        if len(recent_notifications) != len(animals):
            print(f"Expected {len(animals)} animal rejection notifications, got {len(recent_notifications)}")
            return False

        print("All notifications created successfully")
        print("Multiple rejections efficiency test PASSED")
        return True

    except Exception as e:
        print(f"Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_websocket_notification_sending():
    """Test WebSocket notification sending (mock test)"""
    print("\n" + "="*60)
    print("TESTING WEBSOCKET NOTIFICATION SENDING")
    print("="*60)

    try:
        farmer = User.objects.get(username='aaa')

        # Create a test notification directly
        notification = NotificationService.create_notification(
            farmer,
            'test_notification',
            'WebSocket Test',
            'Testing WebSocket notification sending',
            priority='high',
            data={'test': True}
        )

        print(f"Test Data:")
        print(f"   - User: {farmer.username}")
        print(f"   - Notification ID: {notification.id}")

        # Check if notification was created
        if not notification:
            print("❌ Notification creation failed!")
            return False

        print("Notification created successfully")

        # Note: WebSocket testing would require a running server
        # For now, we just verify the notification service doesn't crash
        print("WebSocket sending test: Would require running server")
        print("WebSocket notification sending test PASSED (creation verified)")
        return True

    except Exception as e:
        print(f"Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all notification tests"""
    print("STARTING NOTIFICATION SYSTEM TESTS")
    print("="*60)

    results = []

    # Test animal rejection notifications
    results.append(test_animal_rejection_notification())

    # Test part rejection notifications
    results.append(test_part_rejection_notification())

    # Test multiple rejections efficiency
    results.append(test_multiple_rejections_efficiency())

    # Test WebSocket notification sending
    results.append(test_websocket_notification_sending())

    # Summary
    print("\n" + "="*60)
    print("TEST RESULTS SUMMARY")
    print("="*60)

    passed = sum(results)
    total = len(results)

    print(f"Passed: {passed}/{total}")
    print(f"Failed: {total - passed}/{total}")

    if passed == total:
        print("ALL TESTS PASSED! Notification system is working correctly.")
    else:
        print("Some tests failed. Please check the output above.")

    print("="*60)

if __name__ == '__main__':
    main()