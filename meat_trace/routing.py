"""
WebSocket URL routing configuration for the MeatTrace application.
"""

from django.urls import re_path
from meat_trace.consumers import (
    NotificationConsumer,
    SystemAlertConsumer,
    ProcessingUpdateConsumer,
    AuthProgressConsumer,
    AdminNotificationConsumer,
)

websocket_urlpatterns = [
    # Authentication progress updates (unauthenticated, session-based)
    re_path(r'ws/auth/progress/(?P<session_id>[^/]+)/$', AuthProgressConsumer.as_asgi()),
    
    # User notifications (authenticated)
    re_path(r'ws/notifications/$', NotificationConsumer.as_asgi()),
    
    # System-wide alerts (authenticated)
    re_path(r'ws/alerts/$', SystemAlertConsumer.as_asgi()),
    
    # Processing unit updates (authenticated, role-based)
    re_path(r'ws/processing/$', ProcessingUpdateConsumer.as_asgi()),
    
    # Admin dashboard updates (admin-only)
    re_path(r'ws/admin/$', AdminNotificationConsumer.as_asgi()),
]
