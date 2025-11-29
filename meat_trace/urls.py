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

try:
    from .views import ProcessingUnitViewSet
    router.register(r'processing-units', ProcessingUnitViewSet, basename='processing-units')
except Exception:
    # Optional registration
    pass

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
    print("[OK] AdminDashboardViewSet registered successfully")
except Exception as e:
    print(f"[ERROR] Failed to register AdminDashboardViewSet: {e}")

try:
    from .viewsets import AdminUserViewSet
    router.register(r'admin/users', AdminUserViewSet, basename='admin-users')
    print("[OK] AdminUserViewSet registered successfully")
except Exception as e:
    print(f"[ERROR] Failed to register AdminUserViewSet: {e}")

try:
    from .viewsets import AdminProcessingUnitViewSet
    router.register(r'admin/processing-units', AdminProcessingUnitViewSet, basename='admin-processing-units')
    print("[OK] AdminProcessingUnitViewSet registered successfully")
except Exception as e:
    print(f"[ERROR] Failed to register AdminProcessingUnitViewSet: {e}")

try:
    from .viewsets import AdminShopViewSet
    router.register(r'admin/shops', AdminShopViewSet, basename='admin-shops')
    print("[OK] AdminShopViewSet registered successfully")
except Exception as e:
    print(f"[ERROR] Failed to register AdminShopViewSet: {e}")

try:
    from .viewsets import AdminAnimalViewSet
    router.register(r'admin/animals', AdminAnimalViewSet, basename='admin-animals')
    print("[OK] AdminAnimalViewSet registered successfully")
except Exception as e:
    print(f"[ERROR] Failed to register AdminAnimalViewSet: {e}")

try:
    from .viewsets import AdminProductViewSet
    router.register(r'admin/products', AdminProductViewSet, basename='admin-products')
    print("[OK] AdminProductViewSet registered successfully")
except Exception as e:
    print(f"[ERROR] Failed to register AdminProductViewSet: {e}")

try:
    from .viewsets import AdminAnalyticsViewSet
    router.register(r'admin/analytics', AdminAnalyticsViewSet, basename='admin-analytics')
    print("[OK] AdminAnalyticsViewSet registered successfully")
except Exception as e:
    print(f"[ERROR] Failed to register AdminAnalyticsViewSet: {e}")

urlpatterns = [
    # Admin template routes were moved to `meat_trace.admin_urls` so the
    # admin UI can be included only in environments that need it.
    # To enable the admin templates mount them in your project URLs:
    #     path('site-admin/', include('meat_trace.admin_urls'))
    # This keeps the main `meat_trace.urls` import lighter for API-only envs.

    # JWT Authentication endpoints
    path('api/v2/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/v2/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('api/v2/health/', views.health_check, name='health_check'),
    path('api/v2/dashboard/', views.dashboard_view, name='dashboard'),
    path('api/v2/activities/', views.activities_view, name='activities'),
    path('api/v2/farmer/dashboard/', views.farmer_dashboard, name='farmer_dashboard'),
    path('api/v2/production-stats/', views.production_stats_view, name='production_stats'),
    path('api/v2/processing-pipeline/', views.processing_pipeline_view, name='processing_pipeline'),

    # Product info endpoints
    path('api/v2/product-info/view/<int:product_id>/', views.product_info_view, name='product_info_view'),
    path('api/v2/product-info/list/', views.product_info_list_view, name='product_info_list'),

    # Processing Unit dashboard endpoints
    path('processor/add-product-category/', views.add_product_category, name='add_product_category'),

    # path('api/v2/processing-unit-users/<int:unit_id>/', views.AdminProcessingUnitViewSet.as_view({'get': 'users'}), name='processing-unit-users'),
]

# Include router URLs for all registered viewsets
urlpatterns += [
    path('api/v2/', include(router.urls)),
]