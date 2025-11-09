"""
URL configuration for meattrace_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from rest_framework.authtoken import views as authtoken_views
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

schema_view = get_schema_view(
    openapi.Info(
        title="Meat Trace API",
        default_version='v1',
        description="API for meat traceability system",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="contact@meattrace.local"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    # Backwards-compatibility redirect: old app-level admin dashboard paths
    path('admin/dashboard/', RedirectView.as_view(url='/site-admin/dashboard/', permanent=False)),
    path('', include('meat_trace.urls')),
    path('api-token-auth/', authtoken_views.obtain_auth_token),
    # Legacy drf-yasg documentation (keeping for backward compatibility)
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    # New drf-spectacular documentation (preferred)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# Serve static and media files (both development and production)
# Note: In production, it's better to use a proper web server (Nginx/Apache) to serve static files
# But this works for both environments
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
