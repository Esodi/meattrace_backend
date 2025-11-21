"""
NotificationService provides centralized notification management for the meat traceability app.
Handles creating, sending, and managing notifications with enhanced features like priority,
grouping, batch notifications, real-time delivery, multi-channel support, templates,
rate limiting, retry logic, and delivery tracking.
"""

from django.utils import timezone
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings
import requests
import json
import logging

try:
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    CHANNELS_AVAILABLE = True
except ImportError:
    CHANNELS_AVAILABLE = False

from ..models import (
    Notification, User, NotificationTemplate, NotificationChannel,
    NotificationDelivery, NotificationRateLimit, NotificationSchedule
)

logger = logging.getLogger(__name__)


class NotificationService:
    """Service class for managing notifications"""

    @staticmethod
    def create_notification(user, notification_type, title, message, **kwargs):
        """
        Create a single notification with enhanced features including templates and multi-channel delivery.

        Args:
            user: User instance to receive the notification
            notification_type: Type of notification (from NOTIFICATION_TYPE_CHOICES)
            title: Notification title (or template name if using template)
            message: Notification message (or template variables if using template)
            **kwargs: Additional options:
                 - priority: 'low', 'medium', 'high', 'urgent' (default: 'medium')
                 - action_type: Action type for the notification (default: 'none')
                 - action_url: URL for action (optional)
                 - action_text: Text for action button (optional)
                 - data: Additional JSON data (optional)
                 - expires_at: Expiration datetime (optional)
                 - group_key: Key to group related notifications (optional)
                 - is_batch_notification: Whether this is part of a batch (default: False)
                 - template_name: Name of template to use (optional)
                 - template_vars: Variables for template rendering (optional)
                 - channels: List of channel names to send via (optional)
                 - schedule: NotificationSchedule instance for scheduled notifications (optional)

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
        template_name = kwargs.get('template_name')
        template_vars = kwargs.get('template_vars', {})
        channels = kwargs.get('channels', None)
        schedule = kwargs.get('schedule')

        # Handle template rendering
        template = None
        if template_name:
            try:
                template = NotificationTemplate.objects.get(name=template_name, is_active=True)
                # If using template, title and message are treated as template variables
                template_context = {**template_vars, **kwargs}
                title = template.render_subject(template_context) or title
                message = template.render_content(template_context)
            except NotificationTemplate.DoesNotExist:
                logger.warning(f"Template '{template_name}' not found, using raw title/message")

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
            is_batch_notification=is_batch_notification,
            template=template,
            schedule=schedule
        )

        # Send via specified channels or default channels
        notification.send_via_channels(channels)

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
    def send_via_channel(notification, channel):
        """
        Send notification via a specific channel with rate limiting and retry logic.

        Args:
            notification: Notification instance
            channel: NotificationChannel instance
        """
        # Check rate limiting
        rate_limit, created = NotificationRateLimit.objects.get_or_create(
            user=notification.user,
            channel=channel,
            defaults={'minute_count': 0, 'hour_count': 0, 'day_count': 0}
        )

        if rate_limit.increment_and_check():
            logger.warning(f"Rate limit exceeded for user {notification.user.username} on channel {channel.name}")
            return

        # Create delivery record
        delivery = NotificationDelivery.objects.create(
            notification=notification,
            channel=channel,
            recipient=notification.user
        )

        try:
            # Send via appropriate channel
            if channel.channel_type == 'email':
                NotificationService._send_email(notification, channel, delivery)
            elif channel.channel_type == 'sms':
                NotificationService._send_sms(notification, channel, delivery)
            elif channel.channel_type == 'push':
                NotificationService._send_push(notification, channel, delivery)
            elif channel.channel_type == 'in_app':
                # In-app notifications are already handled by the notification creation
                delivery.mark_sent()

        except Exception as e:
            logger.error(f"Failed to send notification via {channel.name}: {str(e)}")
            delivery.mark_failed(str(e))

    @staticmethod
    def _send_email(notification, channel, delivery):
        """Send email notification"""
        try:
            config = channel.config
            subject = notification.title
            message = notification.message
            from_email = config.get('from_email', getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'))
            recipient_list = [notification.user.email]

            # Use template if available
            if notification.template and notification.template.template_type == 'email':
                subject = notification.template.render_subject(notification.data)
                message = notification.template.render_content(notification.data)

            send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=recipient_list,
                fail_silently=False
            )

            delivery.mark_sent()

        except Exception as e:
            delivery.mark_failed(str(e))

    @staticmethod
    def _send_sms(notification, channel, delivery):
        """Send SMS notification"""
        try:
            config = channel.config
            provider = config.get('provider', 'twilio')  # Default to Twilio

            if provider == 'twilio':
                NotificationService._send_twilio_sms(notification, channel, delivery)
            elif provider == 'africas_talking':
                NotificationService._send_africas_talking_sms(notification, channel, delivery)
            else:
                raise ValueError(f"Unsupported SMS provider: {provider}")

        except Exception as e:
            delivery.mark_failed(str(e))

    @staticmethod
    def _send_twilio_sms(notification, channel, delivery):
        """Send SMS via Twilio"""
        config = channel.config
        account_sid = config.get('account_sid')
        auth_token = config.get('auth_token')
        from_number = config.get('from_number')

        if not all([account_sid, auth_token, from_number]):
            raise ValueError("Twilio configuration incomplete")

        try:
            from twilio.rest import Client
            client = Client(account_sid, auth_token)

            message = client.messages.create(
                body=notification.message,
                from_=from_number,
                to=notification.user.profile.phone if notification.user.profile.phone else ''
            )

            delivery.mark_sent(message.sid)

        except ImportError:
            raise ValueError("Twilio package not installed")
        except Exception as e:
            raise e

    @staticmethod
    def _send_africas_talking_sms(notification, channel, delivery):
        """Send SMS via Africa's Talking"""
        config = channel.config
        username = config.get('username')
        api_key = config.get('api_key')
        sender_id = config.get('sender_id', 'MEATTRACE')

        if not all([username, api_key]):
            raise ValueError("Africa's Talking configuration incomplete")

        try:
            # Africa's Talking SMS API
            url = "https://api.africastalking.com/version1/messaging"
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/x-www-form-urlencoded',
                'apiKey': api_key
            }

            data = {
                'username': username,
                'to': notification.user.profile.phone if notification.user.profile.phone else '',
                'message': notification.message,
                'from': sender_id
            }

            response = requests.post(url, headers=headers, data=data)
            response.raise_for_status()

            result = response.json()
            if result.get('SMSMessageData', {}).get('Recipients'):
                recipient = result['SMSMessageData']['Recipients'][0]
                delivery.mark_sent(recipient.get('messageId'))
            else:
                raise ValueError("SMS sending failed")

        except Exception as e:
            raise e

    @staticmethod
    def _send_push(notification, channel, delivery):
        """Send push notification"""
        try:
            config = channel.config
            provider = config.get('provider', 'fcm')  # Default to Firebase Cloud Messaging

            if provider == 'fcm':
                NotificationService._send_fcm_push(notification, channel, delivery)
            else:
                raise ValueError(f"Unsupported push provider: {provider}")

        except Exception as e:
            delivery.mark_failed(str(e))

    @staticmethod
    def _send_fcm_push(notification, channel, delivery):
        """Send push notification via Firebase Cloud Messaging"""
        config = channel.config
        server_key = config.get('server_key')

        if not server_key:
            raise ValueError("FCM server key not configured")

        try:
            url = "https://fcm.googleapis.com/fcm/send"
            headers = {
                'Authorization': f'key={server_key}',
                'Content-Type': 'application/json'
            }

            # Get user's FCM token (assuming it's stored in user profile or device model)
            fcm_token = getattr(notification.user.profile, 'fcm_token', None)
            if not fcm_token:
                raise ValueError("User has no FCM token")

            data = {
                'to': fcm_token,
                'notification': {
                    'title': notification.title,
                    'body': notification.message,
                    'icon': 'ic_notification',
                    'click_action': notification.action_url or 'FLUTTER_NOTIFICATION_CLICK'
                },
                'data': {
                    'notification_id': str(notification.id),
                    'type': notification.notification_type,
                    'priority': notification.priority,
                    'click_action': notification.action_url or ''
                }
            }

            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()

            result = response.json()
            if result.get('success') == 1:
                delivery.mark_sent(result.get('multicast_id'))
            else:
                raise ValueError(f"FCM send failed: {result}")

        except Exception as e:
            raise e

    @staticmethod
    def broadcast_notification(notification_type, title, message, user_filters=None, channels=None, **kwargs):
        """
        Broadcast notification to multiple users based on filters.

        Args:
            notification_type: Type of notification
            title: Notification title
            message: Notification message
            user_filters: Dict of filters to apply to User queryset (optional)
            channels: List of channel names to send via (optional)
            **kwargs: Additional notification options
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()

        queryset = User.objects.all()

        # Apply filters
        if user_filters:
            queryset = queryset.filter(**user_filters)

        notifications = []
        for user in queryset:
            try:
                notification = NotificationService.create_notification(
                    user=user,
                    notification_type=notification_type,
                    title=title,
                    message=message,
                    channels=channels,
                    **kwargs
                )
                notifications.append(notification)
            except Exception as e:
                logger.error(f"Failed to create notification for user {user.username}: {str(e)}")

        return notifications

    @staticmethod
    def process_scheduled_notifications():
        """
        Process all scheduled notifications that are due to be sent.
        Should be called periodically (e.g., via Celery beat).
        """
        now = timezone.now()
        due_schedules = NotificationSchedule.objects.filter(
            is_active=True,
            scheduled_at__lte=now
        )

        sent_count = 0
        for schedule in due_schedules:
            try:
                # Get recipients
                recipients = list(schedule.recipient_users.all())

                # Add users from groups (simplified - in production you'd have proper group management)
                if schedule.recipient_groups:
                    from django.contrib.auth import get_user_model
                    User = get_user_model()

                    for group in schedule.recipient_groups:
                        if group == 'farmers':
                            recipients.extend(User.objects.filter(profile__role='Farmer'))
                        elif group == 'processors':
                            recipients.extend(User.objects.filter(profile__role='Processor'))
                        elif group == 'shop_owners':
                            recipients.extend(User.objects.filter(profile__role='ShopOwner'))
                        elif group == 'admins':
                            recipients.extend(User.objects.filter(profile__role='Admin'))

                # Remove duplicates
                recipients = list(set(recipients))

                # Send to each recipient
                for user in recipients:
                    try:
                        NotificationService.create_notification(
                            user=user,
                            notification_type=schedule.notification_type,
                            title=schedule.title_template,
                            message=schedule.message_template,
                            template_vars=schedule.template_variables,
                            channels=list(schedule.channels.all()),
                            schedule=schedule
                        )
                        sent_count += 1
                    except Exception as e:
                        logger.error(f"Failed to send scheduled notification to {user.username}: {str(e)}")

                # Update schedule for recurring notifications
                if schedule.schedule_type == 'recurring':
                    if schedule.frequency == 'daily':
                        schedule.scheduled_at = schedule.scheduled_at + timezone.timedelta(days=1)
                    elif schedule.frequency == 'weekly':
                        schedule.scheduled_at = schedule.scheduled_at + timezone.timedelta(weeks=1)
                    elif schedule.frequency == 'monthly':
                        # Add one month (simplified)
                        year = schedule.scheduled_at.year
                        month = schedule.scheduled_at.month + 1
                        if month > 12:
                            month = 1
                            year += 1
                        day = min(schedule.scheduled_at.day, 28)  # Handle February
                        schedule.scheduled_at = schedule.scheduled_at.replace(year=year, month=month, day=day)
                    schedule.save()
                else:
                    # One-time schedule, deactivate
                    schedule.is_active = False
                    schedule.save()

            except Exception as e:
                logger.error(f"Failed to process scheduled notification {schedule.title}: {str(e)}")

        return sent_count

    @staticmethod
    def retry_failed_deliveries():
        """
        Retry failed notification deliveries.
        Should be called periodically (e.g., via Celery beat).
        """
        now = timezone.now()
        failed_deliveries = NotificationDelivery.objects.filter(
            status='retrying',
            next_retry_at__lte=now
        ).select_related('notification', 'channel', 'recipient')

        retried_count = 0
        for delivery in failed_deliveries:
            try:
                NotificationService.send_via_channel(delivery.notification, delivery.channel)
                retried_count += 1
            except Exception as e:
                logger.error(f"Retry failed for delivery {delivery.id}: {str(e)}")
                delivery.retry_count += 1
                if delivery.retry_count >= delivery.max_retries:
                    delivery.status = 'failed'
                else:
                    # Schedule next retry with exponential backoff
                    delay_minutes = 5 * (2 ** delivery.retry_count)
                    delivery.next_retry_at = now + timezone.timedelta(minutes=delay_minutes)
                delivery.save()

        return retried_count

    @staticmethod
    def get_delivery_analytics(start_date=None, end_date=None):
        """
        Get delivery analytics for notifications.

        Args:
            start_date: Start date for analytics (optional)
            end_date: End date for analytics (optional)

        Returns:
            Dict with delivery analytics
        """
        queryset = NotificationDelivery.objects.all()

        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)

        total_deliveries = queryset.count()
        if total_deliveries == 0:
            return {
                'total_deliveries': 0,
                'successful_deliveries': 0,
                'failed_deliveries': 0,
                'pending_deliveries': 0,
                'success_rate': 0,
                'channel_breakdown': {},
                'retry_stats': {}
            }

        successful = queryset.filter(status='delivered').count()
        failed = queryset.filter(status='failed').count()
        pending = queryset.filter(status__in=['pending', 'retrying']).count()

        # Channel breakdown
        channel_stats = queryset.values('channel__name', 'channel__channel_type').annotate(
            total=Count('id'),
            successful=Count('id', filter=Q(status='delivered')),
            failed=Count('id', filter=Q(status='failed'))
        )

        # Retry statistics
        retry_stats = queryset.filter(retry_count__gt=0).aggregate(
            total_retries=Count('id'),
            avg_retry_count=Avg('retry_count'),
            max_retry_count=Max('retry_count')
        )

        return {
            'total_deliveries': total_deliveries,
            'successful_deliveries': successful,
            'failed_deliveries': failed,
            'pending_deliveries': pending,
            'success_rate': round((successful / total_deliveries) * 100, 2),
            'channel_breakdown': list(channel_stats),
            'retry_stats': retry_stats
        }

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
    def notify_product_rejected(processor_user, product, shop, quantity_rejected, rejection_reason):
        """Send notification to processor when shop rejects a product"""
        return NotificationService.create_notification(
            processor_user,
            'product_rejected',
            f'Product {product.name} rejected by shop',
            f'Shop {shop.name} rejected {quantity_rejected} units of {product.name} (Batch: {product.batch_number}). Reason: {rejection_reason}',
            priority='high',
            action_type='view',
            data={
                'product_id': product.id,
                'product_name': product.name,
                'batch_number': product.batch_number,
                'shop_id': shop.id,
                'shop_name': shop.name,
                'quantity_rejected': float(quantity_rejected),
                'rejection_reason': rejection_reason
            }
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