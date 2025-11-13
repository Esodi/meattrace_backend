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

# Admin viewsets removed - admin implementation removed from project
# try:
#     from .views import AdminProcessingUnitViewSet as ProcessingUnitViewSet
#     router.register(r'processing-units', ProcessingUnitViewSet, basename='processing-units')
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

try:
    from .views import SaleViewSet
    router.register(r'sales', SaleViewSet, basename='sales')
except Exception:
    # Optional registration
    pass

try:
    from .views import NotificationViewSet
    router.register(r'notifications', NotificationViewSet, basename='notifications')
except Exception:
    # Optional registration
    pass

try:
    from .views import SlaughterPartViewSet
    router.register(r'slaughter-parts', SlaughterPartViewSet, basename='slaughter-parts')
except Exception:
    # Optional registration
    pass

try:
    from .viewsets import SystemConfigurationViewSet
    router.register(r'config/system', SystemConfigurationViewSet, basename='system-config')
except Exception:
    # Optional registration
    pass

try:
    from .viewsets import FeatureFlagViewSet
    router.register(r'config/feature-flags', FeatureFlagViewSet, basename='feature-flags')
except Exception:
    # Optional registration
    pass

# ══════════════════════════════════════════════════════════════════════════════
# ADMIN DASHBOARD URL PATTERNS
# ══════════════════════════════════════════════════════════════════════════════

try:
    from .viewsets import AdminDashboardViewSet
    router.register(r'admin/dashboard', AdminDashboardViewSet, basename='admin-dashboard')
    print("✓ AdminDashboardViewSet registered successfully")
except Exception as e:
    print(f"✗ Failed to register AdminDashboardViewSet: {e}")

try:
    from .viewsets import AdminUserViewSet
    router.register(r'admin/users', AdminUserViewSet, basename='admin-users')
    print("✓ AdminUserViewSet registered successfully")
except Exception as e:
    print(f"✗ Failed to register AdminUserViewSet: {e}")

try:
    from .viewsets import AdminProcessingUnitViewSet
    router.register(r'admin/processing-units', AdminProcessingUnitViewSet, basename='admin-processing-units')
    print("✓ AdminProcessingUnitViewSet registered successfully")
except Exception as e:
    print(f"✗ Failed to register AdminProcessingUnitViewSet: {e}")

try:
    from .viewsets import AdminShopViewSet
    router.register(r'admin/shops', AdminShopViewSet, basename='admin-shops')
    print("✓ AdminShopViewSet registered successfully")
except Exception as e:
    print(f"✗ Failed to register AdminShopViewSet: {e}")

try:
    from .viewsets import AdminAnimalViewSet
    router.register(r'admin/animals', AdminAnimalViewSet, basename='admin-animals')
    print("✓ AdminAnimalViewSet registered successfully")
except Exception as e:
    print(f"✗ Failed to register AdminAnimalViewSet: {e}")

try:
    from .viewsets import AdminProductViewSet
    router.register(r'admin/products', AdminProductViewSet, basename='admin-products')
    print("✓ AdminProductViewSet registered successfully")
except Exception as e:
    print(f"✗ Failed to register AdminProductViewSet: {e}")

try:
    from .viewsets import AdminAnalyticsViewSet
    router.register(r'admin/analytics', AdminAnalyticsViewSet, basename='admin-analytics')
    print("✓ AdminAnalyticsViewSet registered successfully")
except Exception as e:
    print(f"✗ Failed to register AdminAnalyticsViewSet: {e}")

urlpatterns = [
    # Admin template routes were moved to `meat_trace.admin_urls` so the
    # admin UI can be included only in environments that need it.
    # To enable the admin templates mount them in your project URLs:
    #     path('site-admin/', include('meat_trace.admin_urls'))
    # This keeps the main `meat_trace.urls` import lighter for API-only envs.

    # JWT Authentication endpoints
    path('api/v2/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/v2/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Registration and custom auth endpoints
    path('api/v2/register/', RegisterView.as_view(), name='register'),
    path('api/v2/auth/register/', RegisterView.as_view(), name='auth_register'),
    path('api/v2/auth/login/', CustomAuthLoginView.as_view(), name='auth_login'),
    path('api/v2/auth/token/refresh/', TokenRefreshView.as_view(), name='auth_token_refresh'),
    
    # Public endpoints for registration (no authentication required)
    # path('api/v2/public/processing-units/', views.public_processing_units_list, name='public_processing_units'),
    # path('api/v2/public/shops/', views.public_shops_list, name='public_shops'),

    # Custom join-request endpoints
    # path('api/v2/join-requests/create/<int:entity_id>/<str:request_type>/', views.JoinRequestCreateView.as_view(), name='join_request_create'),
    # path('api/v2/join-requests/review/<int:request_id>/', views.JoinRequestReviewView.as_view(), name='join_request_review'),

    # User profile endpoint (for compatibility with Flutter app)
    # path('api/v2/profile/', views.user_profile_view, name='user_profile'),

     # Dashboard endpoints (generic and role-specific)
    # path('api/v2/health/', views.health_check, name='health_check'),
    # path('api/v2/dashboard/', views.dashboard_view, name='dashboard'),
    # path('api/v2/activities/', views.activities_view, name='activities'),
    # path('api/v2/farmer/dashboard/', views.farmer_dashboard, name='farmer_dashboard'),

    # Processing Unit dashboard endpoints
    # Product info HTML view endpoint
    # path('api/v2/product-info/view/<int:product_id>/', views.product_info_view, name='product_info_view'),

    # Processing Unit dashboard endpoints
    # path('processor/add-product-category/', views.add_product_category, name='add_product_category'),
    # Processing Unit dashboard endpoints
    # HTML product info view (renders detailed product page)
    # path('api/v2/product-info/view/<int:product_id>/', views.product_info_view, name='product_info'),
    # path('api/v2/product-info/list/', views.product_info_list_view, name='product_info_list'),

    # Sale info HTML view
    # path('api/v2/sale-info/view/<int:sale_id>/', views.sale_info_view, name='sale_info_view'),

    # Rejection and appeal endpoints
    # path('api/v2/rejection-reasons/', views.rejection_reasons_view, name='rejection_reasons'),
    # Production stats and processing pipeline endpoints
    # path('api/v2/production-stats/', views.production_stats_view, name='production_stats'),
    # path('api/v2/processing-pipeline/', views.processing_pipeline_view, name='processing_pipeline'),
    # path('api/v2/appeal-rejection/', views.appeal_rejection_view, name='appeal_rejection'),

    # Legacy/compat endpoint for frontend settings screen to list processing unit users - removed with admin implementation
    # path('api/v2/processing-unit-users/<int:unit_id>/', views.AdminProcessingUnitViewSet.as_view({'get': 'users'}), name='processing-unit-users'),

    # API router (DRF) - exposes /api/v2/animals/, /api/v2/activities/, /api/v2/profile/, etc.
    path('api/v2/', include((router.urls, 'meat_trace'), namespace='api-v2')),
]