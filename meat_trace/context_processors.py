from django.conf import settings

def site_url(request):
    """Add SITE_URL to template context"""
    return {
        'SITE_URL': getattr(settings, 'SITE_URL', 'http://localhost:8000'),
    }