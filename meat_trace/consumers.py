"""
WebSocket consumers for real-time notifications and updates.
"""

import json

try:
    from channels.generic.websocket import AsyncWebsocketConsumer
    from channels.db import database_sync_to_async
    CHANNELS_AVAILABLE = True
except ImportError:
    CHANNELS_AVAILABLE = False
    # Create a dummy consumer if channels is not available
    class AsyncWebsocketConsumer:
        pass
    def database_sync_to_async(func):
        return func

from django.contrib.auth.models import User
from .models import Notification


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time notifications.
    Users connect to receive live notification updates.
    """

    async def connect(self):
        """Handle WebSocket connection"""
        self.user = self.scope['user']

        if not self.user.is_authenticated:
            await self.close()
            return

        # Join user's notification group
        self.notification_group = f'notifications_{self.user.id}'
        await self.channel_layer.group_add(
            self.notification_group,
            self.channel_name
        )

        await self.accept()

        # Send initial notification stats
        stats = await self.get_notification_stats()
        await self.send(text_data=json.dumps({
            'type': 'initial_stats',
            'stats': stats
        }))

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        if hasattr(self, 'notification_group'):
            await self.channel_layer.group_discard(
                self.notification_group,
                self.channel_name
            )

    async def notification_event(self, event):
        """
        Handle notification events from the NotificationService.
        This method is called when notifications are created, updated, or modified.
        """
        event_type = event['event_type']
        notification_data = event['notification']

        # Send notification to WebSocket
        await self.send(text_data=json.dumps({
            'type': event_type,
            'notification': notification_data
        }))

        # If it's a new notification, also send updated stats
        if event_type == 'notification_created':
            stats = await self.get_notification_stats()
            await self.send(text_data=json.dumps({
                'type': 'stats_updated',
                'stats': stats
            }))

    @database_sync_to_async
    def get_notification_stats(self):
        """Get current notification statistics for the user"""
        from .utils.notification_service import NotificationService
        return NotificationService.get_user_notification_stats(self.user)


class SystemAlertConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for system-wide alerts and announcements.
    All authenticated users receive system alerts.
    """

    async def connect(self):
        """Handle WebSocket connection"""
        self.user = self.scope['user']

        if not self.user.is_authenticated:
            await self.close()
            return

        # Join system alerts group
        await self.channel_layer.group_add(
            'system_alerts',
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        await self.channel_layer.group_discard(
            'system_alerts',
            self.channel_name
        )

    async def system_alert(self, event):
        """
        Handle system alert events.
        """
        alert_data = event['alert']

        await self.send(text_data=json.dumps({
            'type': 'system_alert',
            'alert': alert_data
        }))


class ProcessingUpdateConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time processing updates.
    Processing unit users receive updates about their operations.
    """

    async def connect(self):
        """Handle WebSocket connection"""
        self.user = self.scope['user']

        if not self.user.is_authenticated:
            await self.close()
            return

        # Check if user is a processing unit user
        try:
            profile = await self.get_user_profile()
            if profile.get('role') != 'processing_unit':
                await self.close()
                return

            processing_unit_id = profile.get('processing_unit_id')
            if not processing_unit_id:
                await self.close()
                return

            # Join processing unit's update group
            self.processing_group = f'processing_unit_{processing_unit_id}'
            await self.channel_layer.group_add(
                self.processing_group,
                self.channel_name
            )

            await self.accept()

        except Exception:
            await self.close()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        if hasattr(self, 'processing_group'):
            await self.channel_layer.group_discard(
                self.processing_group,
                self.channel_name
            )

    async def processing_update(self, event):
        """
        Handle processing update events.
        """
        update_data = event['update']

        await self.send(text_data=json.dumps({
            'type': 'processing_update',
            'update': update_data
        }))

    @database_sync_to_async
    def get_user_profile(self):
        """Get user profile data"""
        try:
            profile = self.user.profile
            return {
                'role': profile.role,
                'processing_unit_id': profile.processing_unit.id if profile.processing_unit else None
            }
        except:
            return {'role': None, 'processing_unit_id': None}