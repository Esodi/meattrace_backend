"""
NotificationService provides centralized notification management for the meat traceability app.
Handles creating, sending, and managing notifications with enhanced features like priority,
grouping, batch notifications, and real-time delivery.
"""

from django.utils import timezone
from django.db import transaction
try:
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    CHANNELS_AVAILABLE = True
except ImportError:
    CHANNELS_AVAILABLE = False
from ..models import Notification, User
import json


class NotificationService:
    """Service class for managing notifications"""

    @staticmethod
    def create_notification(user, notification_type, title, message, **kwargs):
        """
        Create a single notification with enhanced features.

        Args:
            user: User instance to receive the notification
            notification_type: Type of notification (from NOTIFICATION_TYPE_CHOICES)
            title: Notification title
            message: Notification message
            **kwargs: Additional options:
                - priority: 'low', 'medium', 'high', 'urgent' (default: 'medium')
                - action_type: Action type for the notification (default: 'none')
                - action_url: URL for action (optional)
                - action_text: Text for action button (optional)
                - data: Additional JSON data (optional)
                - expires_at: Expiration datetime (optional)
                - group_key: Key to group related notifications (optional)
                - is_batch_notification: Whether this is part of a batch (default: False)

        Returns:
            Notification instance
        """
        priority = kwargs.get('priority', 'medium')
        action_type = kwargs.get('action_type', 'none')
        action_url = kwargs.get('action_url', '')
        action_text = kwargs.get('action_text', '')
        data = kwargs.get('data', {})
        expires_at = kwargs.get('expires_at')
        group_key = kwargs.get('group_key', '')
        is_batch_notification = kwargs.get('is_batch_notification', False)

        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            priority=priority,
            action_type=action_type,
            action_url=action_url,
            action_text=action_text,
            data=data,
            expires_at=expires_at,
            group_key=group_key,
            is_batch_notification=is_batch_notification
        )

        # Send real-time notification via WebSocket
        NotificationService._send_realtime_notification(notification)

        return notification

    @staticmethod
    def create_batch_notifications(notifications_data):
        """
        Create multiple notifications in a batch.

        Args:
            notifications_data: List of dicts, each containing notification data
                Each dict should have: user, notification_type, title, message, and optional kwargs

        Returns:
            List of created Notification instances
        """
        notifications = []

        with transaction.atomic():
            for data in notifications_data:
                user = data.pop('user')
                notification_type = data.pop('notification_type')
                title = data.pop('title')
                message = data.pop('message')

                # Mark as batch notification
                data['is_batch_notification'] = True

                notification = NotificationService.create_notification(
                    user, notification_type, title, message, **data
                )
                notifications.append(notification)

        return notifications

    @staticmethod
    def create_grouped_notification(user, group_key, notification_type, title, message, **kwargs):
        """
        Create a notification that belongs to a group. If a notification with the same
        group_key exists and is unread, it will be updated instead of creating a new one.

        Args:
            user: User instance
            group_key: Unique key for the notification group
            notification_type, title, message: Standard notification fields
            **kwargs: Additional options

        Returns:
            Notification instance (created or updated)
        """
        # Check if there's an existing unread notification in this group
        existing = Notification.objects.filter(
            user=user,
            group_key=group_key,
            is_read=False,
            is_dismissed=False,
            is_archived=False
        ).first()

        if existing:
            # Update existing notification
            existing.title = title
            existing.message = message
            existing.notification_type = notification_type
            existing.created_at = timezone.now()  # Update timestamp

            # Update other fields if provided
            for key, value in kwargs.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)

            existing.save()

            # Send real-time update
            NotificationService._send_realtime_notification(existing, event_type='notification_updated')

            return existing
        else:
            # Create new notification
            kwargs['group_key'] = group_key
            return NotificationService.create_notification(
                user, notification_type, title, message, **kwargs
            )

    @staticmethod
    def mark_as_read(user, notification_ids=None, group_key=None):
        """
        Mark notifications as read.

        Args:
            user: User instance
            notification_ids: List of notification IDs (optional)
            group_key: Group key to mark all in group as read (optional)
        """
        queryset = Notification.objects.filter(user=user, is_read=False)

        if notification_ids:
            queryset = queryset.filter(id__in=notification_ids)
        elif group_key:
            queryset = queryset.filter(group_key=group_key)

        updated_count = queryset.update(is_read=True, read_at=timezone.now())

        # Send real-time updates
        for notification in queryset:
            NotificationService._send_realtime_notification(
                notification, event_type='notification_read'
            )

        return updated_count

    @staticmethod
    def dismiss_notifications(user, notification_ids=None, group_key=None):
        """
        Dismiss notifications.

        Args:
            user: User instance
            notification_ids: List of notification IDs (optional)
            group_key: Group key to dismiss all in group (optional)
        """
        queryset = Notification.objects.filter(user=user, is_dismissed=False)

        if notification_ids:
            queryset = queryset.filter(id__in=notification_ids)
        elif group_key:
            queryset = queryset.filter(group_key=group_key)

        updated_count = queryset.update(is_dismissed=True, dismissed_at=timezone.now())

        # Send real-time updates
        for notification in queryset:
            NotificationService._send_realtime_notification(
                notification, event_type='notification_dismissed'
            )

        return updated_count

    @staticmethod
    def archive_notifications(user, notification_ids=None, group_key=None):
        """
        Archive notifications.

        Args:
            user: User instance
            notification_ids: List of notification IDs (optional)
            group_key: Group key to archive all in group (optional)
        """
        queryset = Notification.objects.filter(user=user, is_archived=False)

        if notification_ids:
            queryset = queryset.filter(id__in=notification_ids)
        elif group_key:
            queryset = queryset.filter(group_key=group_key)

        updated_count = queryset.update(is_archived=True, archived_at=timezone.now())

        # Send real-time updates
        for notification in queryset:
            NotificationService._send_realtime_notification(
                notification, event_type='notification_archived'
            )

        return updated_count

    @staticmethod
    def cleanup_expired_notifications():
        """
        Clean up expired notifications. Should be called periodically.
        """
        expired_count = Notification.objects.filter(
            expires_at__lt=timezone.now(),
            is_archived=False
        ).update(is_archived=True, archived_at=timezone.now())

        return expired_count

    @staticmethod
    def get_user_notification_stats(user):
        """
        Get notification statistics for a user.

        Args:
            user: User instance

        Returns:
            Dict with notification statistics
        """
        base_queryset = Notification.objects.filter(user=user)

        stats = {
            'total': base_queryset.count(),
            'unread': base_queryset.filter(is_read=False).count(),
            'read': base_queryset.filter(is_read=True).count(),
            'dismissed': base_queryset.filter(is_dismissed=True).count(),
            'archived': base_queryset.filter(is_archived=True).count(),
            'by_priority': {
                'urgent': base_queryset.filter(priority='urgent', is_dismissed=False, is_archived=False).count(),
                'high': base_queryset.filter(priority='high', is_dismissed=False, is_archived=False).count(),
                'medium': base_queryset.filter(priority='medium', is_dismissed=False, is_archived=False).count(),
                'low': base_queryset.filter(priority='low', is_dismissed=False, is_archived=False).count(),
            },
            'by_type': {}
        }

        # Count by notification type
        for choice in Notification.NOTIFICATION_TYPE_CHOICES:
            type_key = choice[0]
            count = base_queryset.filter(
                notification_type=type_key,
                is_dismissed=False,
                is_archived=False
            ).count()
            if count > 0:
                stats['by_type'][type_key] = count

        return stats

    @staticmethod
    def _send_realtime_notification(notification, event_type='notification_created'):
        """
        Send notification via WebSocket for real-time updates.

        Args:
            notification: Notification instance
            event_type: Type of event ('notification_created', 'notification_read', etc.)
        """
        if not CHANNELS_AVAILABLE:
            return

        try:
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    f'notifications_{notification.user.id}',
                    {
                        'type': 'notification_event',
                        'event_type': event_type,
                        'notification': {
                            'id': notification.id,
                            'notification_type': notification.notification_type,
                            'title': notification.title,
                            'message': notification.message,
                            'priority': notification.priority,
                            'is_read': notification.is_read,
                            'is_dismissed': notification.is_dismissed,
                            'is_archived': notification.is_archived,
                            'action_type': notification.action_type,
                            'action_url': notification.action_url,
                            'action_text': notification.action_text,
                            'created_at': notification.created_at.isoformat(),
                            'data': notification.data
                        }
                    }
                )
        except Exception as e:
            # Log error but don't fail the notification creation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send real-time notification: {str(e)}")

    # Convenience methods for common notification types

    @staticmethod
    def notify_join_request(owner, requester, entity_type, entity_name):
        """Send notification for join request"""
        return NotificationService.create_notification(
            owner,
            'join_request',
            f'New join request',
            f'{requester.username} requested to join {entity_type} {entity_name}',
            action_type='view',
            data={'requester_id': requester.id, 'entity_type': entity_type, 'entity_name': entity_name}
        )

    @staticmethod
    def notify_join_approved(requester, entity_type, entity_name):
        """Send notification for join request approval"""
        return NotificationService.create_notification(
            requester,
            'join_approved',
            f'Join request approved',
            f'Your request to join {entity_type} {entity_name} has been approved',
            priority='high',
            action_type='view'
        )

    @staticmethod
    def notify_join_rejected(requester, entity_type, entity_name, reason=None):
        """Send notification for join request rejection"""
        message = f'Your request to join {entity_type} {entity_name} has been rejected'
        if reason:
            message += f': {reason}'

        return NotificationService.create_notification(
            requester,
            'join_rejected',
            f'Join request rejected',
            message,
            priority='medium'
        )

    @staticmethod
    def notify_animal_rejected(farmer, animal, category, specific_reason):
        """Send notification for animal rejection"""
        return NotificationService.create_notification(
            farmer,
            'animal_rejected',
            f'Animal {animal.animal_id} rejected',
            f'Your animal {animal.animal_id} was rejected during processing: {category} - {specific_reason}',
            priority='high',
            action_type='appeal',
            data={'animal_id': animal.animal_id, 'category': category, 'specific_reason': specific_reason}
        )

    @staticmethod
    def notify_part_rejected(farmer, part, category, specific_reason):
        """Send notification for slaughter part rejection"""
        return NotificationService.create_notification(
            farmer,
            'part_rejected',
            f'Animal part rejected',
            f'A part ({part.part_type}) of your animal {part.animal.animal_id} was rejected: {category} - {specific_reason}',
            priority='high',
            action_type='appeal',
            data={'animal_id': part.animal.animal_id, 'part_id': part.id, 'part_type': part.part_type, 'category': category, 'specific_reason': specific_reason}
        )

    @staticmethod
    def notify_appeal_submitted(farmer, item_type, item_id, appeal_notes):
        """Send notification for appeal submission"""
        return NotificationService.create_notification(
            farmer,
            'appeal_submitted',
            f'Appeal submitted',
            f'Your appeal for {item_type} has been submitted and is pending review',
            priority='medium',
            data={'item_type': item_type, 'item_id': item_id, 'appeal_notes': appeal_notes}
        )

    @staticmethod
    def notify_appeal_resolved(farmer, item_type, item_id, resolution, notes=None):
        """Send notification for appeal resolution"""
        notification_type = 'appeal_approved' if resolution == 'approved' else 'appeal_denied'
        title = f'Appeal {resolution.title()}'
        message = f'Your appeal for {item_type} has been {resolution}'

        if notes:
            message += f': {notes}'

        priority = 'high' if resolution == 'approved' else 'medium'

        return NotificationService.create_notification(
            farmer,
            notification_type,
            title,
            message,
            priority=priority,
            data={'item_type': item_type, 'item_id': item_id, 'resolution': resolution, 'notes': notes}
        )