"""
Middleware for logging all API requests and responses
"""
import time
import json


class APILoggingMiddleware:
    """Middleware to log all API requests and responses"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Skip logging for static files and admin
        if request.path.startswith('/static/') or request.path.startswith('/media/'):
            return self.get_response(request)
        
        # Log request
        start_time = time.time()
        
        print("┌" + "─" * 78 + "┐")
        print(f"│ 📨 Incoming Request: {request.method} {request.path}")
        print(f"│ 🔍 Query Params: {dict(request.GET)}")
        
        if request.method in ['POST', 'PUT', 'PATCH']:
            try:
                # Only try to read body if it hasn't been read yet
                if hasattr(request, 'content_type') and hasattr(request, 'body'):
                    content_type = request.content_type
                    if 'application/json' in content_type:
                        try:
                            body = json.loads(request.body.decode('utf-8'))
                            print(f"│ 📦 Body (JSON): {body}")
                        except Exception:
                            print(f"│ 📦 Body: Could not parse JSON")
                    elif 'multipart/form-data' in content_type:
                        print(f"│ 📦 Body (Multipart): Contains file uploads")
                    else:
                        print(f"│ 📦 Body: Non-JSON content")
            except Exception as e:
                print(f"│ ⚠️  Could not parse body: {e}")
        
        # Process request (this is where authentication happens)
        response = self.get_response(request)
        
        # Log authenticated user AFTER request processing (when JWT auth has run)
        try:
            user = getattr(request, 'user', None)
            if user and user.is_authenticated:
                print(f"│ 👤 Authenticated User: {user.username}")
            else:
                print(f"│ 👤 User: AnonymousUser")
        except Exception:
            print(f"│ 👤 User: Could not determine")
        
        # Log response
        duration = time.time() - start_time
        status_emoji = "✅" if 200 <= response.status_code < 300 else "⚠️" if 300 <= response.status_code < 400 else "❌"
        
        print(f"│ {status_emoji} Response: {response.status_code} ({duration:.3f}s)")
        
        # Log response data for errors
        if response.status_code >= 400:
            try:
                if hasattr(response, 'data'):
                    print(f"│ 📄 Response Data: {response.data}")
                elif hasattr(response, 'content'):
                    content = response.content.decode('utf-8')[:500]
                    print(f"│ 📄 Response Content: {content}...")
            except Exception as e:
                print(f"│ ⚠️  Could not parse response: {e}")
        
        print("└" + "─" * 78 + "┘\n")
        
        return response
