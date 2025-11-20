"""
Custom exception handler for DRF to provide detailed error logging
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
import traceback


def custom_exception_handler(exc, context):
    """
    Custom exception handler that logs all errors with detailed information
    """
    # Get the standard error response
    response = exception_handler(exc, context)
    
    # Extract request information
    request = context.get('request')
    view = context.get('view')
    
    # Log the error with details
    print("=" * 80)
    print("🔴 [EXCEPTION HANDLER] API Error Occurred")
    print("=" * 80)
    print(f"📍 Endpoint: {request.method} {request.path}")
    print(f"👤 User: {request.user if request and hasattr(request, 'user') else 'Anonymous'}")
    print(f"🎯 View: {view.__class__.__name__ if view else 'Unknown'}")
    print(f"❌ Exception Type: {exc.__class__.__name__}")
    print(f"💬 Exception Message: {str(exc)}")
    
    if request:
        print(f"📦 Request Data: {request.data if hasattr(request, 'data') else 'N/A'}")
        print(f"🔍 Query Params: {request.query_params if hasattr(request, 'query_params') else request.GET}")
    
    # Print full traceback
    print("\n📜 Full Traceback:")
    traceback.print_exc()
    print("=" * 80)
    
    # If no response was generated, create a custom one
    if response is None:
        response = Response({
            'error': str(exc),
            'type': exc.__class__.__name__,
            'detail': 'An unexpected error occurred. Please check server logs.'
        }, status=500)
    else:
        # Add extra information to the response
        if isinstance(response.data, dict):
            response.data['error_type'] = exc.__class__.__name__
    
    return response
