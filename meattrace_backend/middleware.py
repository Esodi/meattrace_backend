"""
Custom middleware for handling invalid HTTP_HOST headers.
"""
from django.core.exceptions import DisallowedHost
from django.http import HttpResponseBadRequest
import logging

logger = logging.getLogger(__name__)


class SuppressDisallowedHostMiddleware:
    """
    Middleware to catch DisallowedHost exceptions and return a 400 Bad Request
    instead of logging errors. This prevents log pollution from bots/scanners
    sending invalid HTTP_HOST headers.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        return self.get_response(request)
    
    def process_exception(self, request, exception):
        if isinstance(exception, DisallowedHost):
            # Log at debug level instead of error
            logger.debug(
                f"Invalid HTTP_HOST header rejected: {exception}. "
                f"Remote address: {request.META.get('REMOTE_ADDR', 'unknown')}"
            )
            # Return a simple 400 Bad Request response
            return HttpResponseBadRequest("Invalid HTTP_HOST header")
        return None
