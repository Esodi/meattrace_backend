"""
ASGI config for meattrace_backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')

# Initialize Django ASGI application early to ensure models are loaded
django_asgi_app = get_asgi_application()

# Import channels and routing after Django is initialized
try:
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.auth import AuthMiddlewareStack
    from meat_trace.routing import websocket_urlpatterns
    
    print("✅ ASGI mode active - WebSocket support enabled")
    print("📡 WebSocket endpoints available:")
    for pattern in websocket_urlpatterns:
        print(f"   - {pattern.pattern}")
    
    application = ProtocolTypeRouter({
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(
            URLRouter(
                websocket_urlpatterns
            )
        ),
    })
except ImportError as e:
    # If channels is not installed, fall back to HTTP only
    print("❌ ASGI mode failed - Falling back to WSGI (HTTP only)")
    print(f"Error: {e}")
    application = django_asgi_app
except Exception as e:
    print(f"❌ ASGI configuration error: {e}")
    application = django_asgi_app
