from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views
from .auth_views import CustomTokenObtainPairView, RegisterView, CustomAuthLoginView


# ═════════════════════════════════════════════════════════════════════════════=
# ADMIN DASHBOARD URL PATTERNS + API ROUTER
# ═════════════════════════════════════════════════════════════════════════════=

router = DefaultRouter()
# Register viewsets (AnimalViewSet is implemented in views.py)
try:
    router.register(r'animals', views.AnimalViewSet, basename='animals')
except Exception:
    # If AnimalViewSet not present at import time, router registration will be skipped
    pass

try:
    router.register(r'activities', views.ActivityViewSet, basename='activities')
except Exception:
    # If ActivityViewSet not present at import time, router registration will be skipped
    pass

try:
    router.register(r'profile', views.UserProfileViewSet, basename='profile')
except Exception:
    # If UserProfileViewSet not present at import time, router registration will be skipped
    pass

# try:
from .views import ProcessingUnitViewSet
router.register(r'processing-units', ProcessingUnitViewSet, basename='processing-units')
# except Exception:
#     # Optional registration
#     pass

try:
    from .views import JoinRequestViewSet
    router.register(r'join-requests', JoinRequestViewSet, basename='join-requests')
except Exception:
    # Optional registration
    pass
try:
    from .views import ShopViewSet
    router.register(r'shops', ShopViewSet, basename='shops')
except Exception:
    # Optional registration
    pass

try:
    from .views import OrderViewSet
    router.register(r'orders', OrderViewSet, basename='orders')
except Exception:
    # Optional registration
    pass

try:
    from .views import ProductViewSet
    router.register(r'products', ProductViewSet, basename='products')
except Exception:
    # Optional registration
    pass

try:
    from .views import ProductCategoryViewSet
    router.register(r'product-categories', ProductCategoryViewSet, basename='product-categories')
except Exception:
    # Optional registration
    pass

try:
    from .views import CarcassMeasurementViewSet
    router.register(r'carcass-measurements', CarcassMeasurementViewSet, basename='carcass-measurements')
except Exception:
    # Optional registration
    pass

urlpatterns = [
    # App-level admin-like template views. Use 'site-admin/' prefix to avoid
    # colliding with Django's built-in admin site which is mounted at '/admin/'.
    path('site-admin/', views.admin_dashboard, name='admin_dashboard'),
    path('site-admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('site-admin/users/', views.admin_users, name='admin_users'),
    path('site-admin/supply-chain/', views.admin_supply_chain, name='admin_supply_chain'),
    path('site-admin/performance/', views.admin_performance, name='admin_performance'),
    path('site-admin/compliance/', views.admin_compliance, name='admin_compliance'),
    path('site-admin/system-health/', views.admin_system_health, name='admin_system_health'),

    # JWT Authentication endpoints
    path('api/v2/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/v2/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Registration and custom auth endpoints
    path('api/v2/register/', RegisterView.as_view(), name='register'),
    path('api/v2/auth/register/', RegisterView.as_view(), name='auth_register'),
    path('api/v2/auth/login/', CustomAuthLoginView.as_view(), name='auth_login'),

    # Custom join-request endpoints
    path('api/v2/join-requests/create/<int:entity_id>/<str:request_type>/', views.JoinRequestCreateView.as_view(), name='join_request_create'),
    path('api/v2/join-requests/review/<int:request_id>/', views.JoinRequestReviewView.as_view(), name='join_request_review'),
    
    # User profile endpoint (for compatibility with Flutter app)
    path('api/v2/profile/', views.user_profile_view, name='user_profile'),

    # Admin API endpoints for real-time data
    path('api/v2/admin/dashboard/data/', views.admin_dashboard_data, name='admin_dashboard_data'),
    path('api/v2/admin/supply-chain/data/', views.admin_supply_chain_data, name='admin_supply_chain_data'),
    path('api/v2/admin/performance/data/', views.admin_performance_data, name='admin_performance_data'),

    # Dashboard endpoints (generic and role-specific)
    path('api/v2/dashboard/', views.dashboard_view, name='dashboard'),
    path('api/v2/activities/', views.activities_view, name='activities'),
    path('api/v2/farmer/dashboard/', views.farmer_dashboard, name='farmer_dashboard'),

    # Processing Unit dashboard endpoints
    # Product info HTML view endpoint
    path('api/v2/product-info/view/<int:product_id>/', views.product_info_view, name='product_info_view'),

    # Processing Unit dashboard endpoints
    path('processor/add-product-category/', views.add_product_category, name='add_product_category'),
    # Processing Unit dashboard endpoints
    # HTML product info view (renders detailed product page)
    path('api/v2/product-info/view/<int:product_id>/', views.product_info_view, name='product_info'),
    path('api/v2/product-info/list/', views.product_info_list_view, name='product_info_list'),
    # Legacy/compat endpoint for frontend settings screen to list processing unit users
    path('api/v2/processing-unit-users/<int:unit_id>/', views.ProcessingUnitViewSet.as_view({'get': 'users'}), name='processing-unit-users'),

    # API router (DRF) - exposes /api/v2/animals/, /api/v2/activities/, /api/v2/profile/, etc.
    path('api/v2/', include((router.urls, 'meat_trace'), namespace='api-v2')),
]