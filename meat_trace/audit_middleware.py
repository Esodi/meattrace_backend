"""
Audit middleware for logging admin actions.
"""
import json
import logging
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


class AdminAuditMiddleware:
    """
    Middleware to log admin actions (POST, PUT, PATCH, DELETE) to UserAuditLog.
    """
    
    ADMIN_URL_PATTERNS = [
        '/api/v2/admin/',
    ]
    
    AUDITED_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE']
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Process the request
        response = self.get_response(request)
        
        # Only log admin actions
        if self._should_audit(request):
            self._log_action(request, response)
        
        return response
    
    def _should_audit(self, request):
        """Check if this request should be audited."""
        if request.method not in self.AUDITED_METHODS:
            return False
        
        if not request.user.is_authenticated:
            return False
        
        for pattern in self.ADMIN_URL_PATTERNS:
            if request.path.startswith(pattern):
                return True
        
        return False
    
    def _log_action(self, request, response):
        """Log the admin action to UserAuditLog."""
        try:
            from meat_trace.models import UserAuditLog
            
            # Extract action details
            action = self._determine_action(request)
            
            # Get request data (sanitized)
            try:
                request_data = json.loads(request.body.decode('utf-8')) if request.body else {}
                # Remove sensitive fields
                for field in ['password', 'token', 'secret']:
                    request_data.pop(field, None)
            except (json.JSONDecodeError, UnicodeDecodeError):
                request_data = {}
            
            # Create audit log entry
            UserAuditLog.objects.create(
                user=request.user,
                action=action,
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                details={
                    'path': request.path,
                    'method': request.method,
                    'status_code': response.status_code,
                    'request_data': request_data,
                }
            )
            
            logger.info(f"[AUDIT] {request.user.username} performed {action} on {request.path}")
            
        except Exception as e:
            logger.error(f"[AUDIT] Failed to log admin action: {e}")
    
    def _determine_action(self, request):
        """Determine a human-readable action name."""
        method_map = {
            'POST': 'CREATE',
            'PUT': 'UPDATE',
            'PATCH': 'PARTIAL_UPDATE',
            'DELETE': 'DELETE',
        }
        
        action = method_map.get(request.method, request.method)
        
        # Extract resource from path
        path_parts = request.path.strip('/').split('/')
        if len(path_parts) >= 3:
            resource = path_parts[-2] if path_parts[-1].isdigit() else path_parts[-1]
            return f"{action}_{resource.upper()}"
        
        return action
    
    def _get_client_ip(self, request):
        """Get the client's IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
