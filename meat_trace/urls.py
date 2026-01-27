from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views
from .auth_views import CustomTokenObtainPairView, RegisterView, CustomAuthLoginView


# ═════════════════════════════════════════════════════════════════════════════=
# ADMIN DASHBOARD URL PATTERNS + API ROUTER
# ═════════════════════════════════════════════════════════════════════════════=

router = DefaultRouter()
import logging
logger = logging.getLogger(__name__)

# Register viewsets (AnimalViewSet is implemented in views.py)
try:
    router.register(r'animals', views.AnimalViewSet, basename='animals')
except Exception as e:
    logger.warning(f"[URL_REGISTRATION] Failed to register AnimalViewSet: {e}")

try:
    router.register(r'activities', views.ActivityViewSet, basename='activities')
except Exception as e:
    logger.warning(f"[URL_REGISTRATION] Failed to register ActivityViewSet: {e}")

try:
    router.register(r'profile', views.UserProfileViewSet, basename='profile')
except Exception as e:
    logger.warning(f"[URL_REGISTRATION] Failed to register UserProfileViewSet: {e}")

try:
    from .views import ProcessingUnitViewSet
    router.register(r'processing-units', ProcessingUnitViewSet, basename='processing-units')
except Exception as e:
    logger.warning(f"[URL_REGISTRATION] Failed to register ProcessingUnitViewSet: {e}")

try:
    from .views import JoinRequestViewSet
    router.register(r'join-requests', JoinRequestViewSet, basename='join-requests')
except Exception as e:
    logger.warning(f"[URL_REGISTRATION] Failed to register JoinRequestViewSet: {e}")
try:
    from .views import ShopViewSet
    router.register(r'shops', ShopViewSet, basename='shops')
except Exception as e:
    logger.warning(f"[URL_REGISTRATION] Failed to register ShopViewSet: {e}")

try:
    from .views import OrderViewSet
    router.register(r'orders', OrderViewSet, basename='orders')
except Exception as e:
    logger.warning(f"[URL_REGISTRATION] Failed to register OrderViewSet: {e}")

try:
    from .views import ProductViewSet
    router.register(r'products', ProductViewSet, basename='products')
except Exception as e:
    logger.warning(f"[URL_REGISTRATION] Failed to register ProductViewSet: {e}")

try:
    from .views import ProductCategoryViewSet
    router.register(r'product-categories', ProductCategoryViewSet, basename='product-categories')
except Exception as e:
    logger.warning(f"[URL_REGISTRATION] Failed to register ProductCategoryViewSet: {e}")

try:
    from .views import CarcassMeasurementViewSet
    router.register(r'carcass-measurements', CarcassMeasurementViewSet, basename='carcass-measurements')
except Exception as e:
    logger.warning(f"[URL_REGISTRATION] Failed to register CarcassMeasurementViewSet: {e}")

try:
    from .views import SaleViewSet
    router.register(r'sales', SaleViewSet, basename='sales')
except Exception as e:
    logger.warning(f"[URL_REGISTRATION] Failed to register SaleViewSet: {e}")

try:
    from .views import InventoryViewSet
    router.register(r'inventory', InventoryViewSet, basename='inventory')
except Exception:
    # Optional registration
    pass

try:
    from .views import ReceiptViewSet
    router.register(r'receipts', ReceiptViewSet, basename='receipts')
except Exception:
    # Optional registration
    pass

try:
    from .views import NotificationViewSet
    router.register(r'notifications', NotificationViewSet, basename='notifications')
except Exception as e:
    logger.warning(f"[URL_REGISTRATION] Failed to register NotificationViewSet: {e}")

try:
    from .views import SlaughterPartViewSet
    router.register(r'slaughter-parts', SlaughterPartViewSet, basename='slaughter-parts')
except Exception as e:
    logger.warning(f"[URL_REGISTRATION] Failed to register SlaughterPartViewSet: {e}")

try:
    from .viewsets import SystemConfigurationViewSet
    router.register(r'config/system', SystemConfigurationViewSet, basename='system-config')
except Exception as e:
    logger.warning(f"[URL_REGISTRATION] Failed to register SystemConfigurationViewSet: {e}")

try:
    from .viewsets import FeatureFlagViewSet
    router.register(r'config/feature-flags', FeatureFlagViewSet, basename='feature-flags')
except Exception as e:
    logger.warning(f"[URL_REGISTRATION] Failed to register FeatureFlagViewSet: {e}")

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
    from .viewsets import AdminSlaughterPartViewSet
    router.register(r'admin/slaughter-parts', AdminSlaughterPartViewSet, basename='admin-slaughter-parts')
    print("[OK] AdminSlaughterPartViewSet registered successfully")
except Exception as e:
    print(f"[ERROR] Failed to register AdminSlaughterPartViewSet: {e}")

try:
    from .viewsets import AdminAbbatoirViewSet
    router.register(r'admin/abbatoirs', AdminAbbatoirViewSet, basename='admin-abbatoirs')
    print("[OK] AdminAbbatoirViewSet registered successfully")
except Exception as e:
    print(f"[ERROR] Failed to register AdminAbbatoirViewSet: {e}")

try:
    from .viewsets import AdminAnalyticsViewSet
    router.register(r'admin/analytics', AdminAnalyticsViewSet, basename='admin-analytics')
    print("[OK] AdminAnalyticsViewSet registered successfully")
except Exception as e:
    print(f"[ERROR] Failed to register AdminAnalyticsViewSet: {e}")

try:
    from .viewsets import AdminComplianceAuditViewSet
    router.register(r'admin/compliance', AdminComplianceAuditViewSet, basename='admin-compliance')
    print("[OK] AdminComplianceAuditViewSet registered successfully")
except Exception as e:
    print(f"[ERROR] Failed to register AdminComplianceAuditViewSet: {e}")

try:
    from .viewsets import AdminCertificationViewSet
    router.register(r'admin/certifications', AdminCertificationViewSet, basename='admin-certifications')
    print("[OK] AdminCertificationViewSet registered successfully")
except Exception as e:
    print(f"[ERROR] Failed to register AdminCertificationViewSet: {e}")

try:
    from .viewsets import RegistrationApplicationViewSet
    router.register(r'admin/registrations', RegistrationApplicationViewSet, basename='admin-registrations')
    print("[OK] RegistrationApplicationViewSet registered successfully")
except Exception as e:
    print(f"[ERROR] Failed to register RegistrationApplicationViewSet: {e}")

try:
    from .viewsets import ApprovalWorkflowViewSet
    router.register(r'admin/workflows', ApprovalWorkflowViewSet, basename='admin-workflows')
    print("[OK] ApprovalWorkflowViewSet registered successfully")
except Exception as e:
    print(f"[ERROR] Failed to register ApprovalWorkflowViewSet: {e}")

urlpatterns = [
    # Admin template routes were moved to `meat_trace.admin_urls` so the
    # admin UI can be included only in environments that need it.
    # To enable the admin templates mount them in your project URLs:
    #     path('site-admin/', include('meat_trace.admin_urls'))
    # This keeps the main `meat_trace.urls` import lighter for API-only envs.

    # JWT Authentication endpoints
    path('api/v2/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/v2/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # User Registration endpoint
    path('api/v2/register/', RegisterView.as_view(), name='register'),
    
    # Auth endpoints (login)
    path('api/v2/auth/login/', CustomAuthLoginView.as_view(), name='auth_login'),
    path('api/v2/login/', CustomAuthLoginView.as_view(), name='login'),
    
    # User profile endpoint (get current authenticated user info)
    path('api/v2/auth/me/', views.user_profile_view, name='auth_me'),
    path('api/v2/profile/me/', views.user_profile_view, name='profile_me'),
    
    # Public endpoints (no authentication required for registration flow)
    path('api/v2/public/processing-units/', views.public_processing_units_list, name='public_processing_units'),
    path('api/v2/public/processing-units/registration/', views.public_processing_units_for_registration, name='public_processing_units_registration'),
    path('api/v2/public/shops/', views.public_shops_list, name='public_shops'),

    path('api/v2/health/', views.health_check, name='health_check'),
    path('api/v2/dashboard/', views.dashboard_view, name='dashboard'),
    path('api/v2/activities/', views.activities_view, name='activities'),
    path('api/v2/abbatoir/dashboard/', views.abbatoir_dashboard, name='abbatoir_dashboard'),
    path('api/v2/production-stats/', views.production_stats_view, name='production_stats'),
    path('api/v2/processing-pipeline/', views.processing_pipeline_view, name='processing_pipeline'),

    # Product info endpoints
    path('api/v2/product-info/view/<int:product_id>/', views.product_info_view, name='product_info_view'),
    path('api/v2/product-info/list/', views.product_info_list_view, name='product_info_list'),
    
    # Sale info endpoint (for QR codes)
    path('api/v2/sale-info/view/<int:sale_id>/', views.sale_info_view, name='sale_info_view'),

    # Processing Unit dashboard endpoints
    path('processor/add-product-category/', views.add_product_category, name='add_product_category'),

    # path('api/v2/processing-unit-users/<int:unit_id>/', views.AdminProcessingUnitViewSet.as_view({'get': 'users'}), name='processing-unit-users'),
]

# Include router URLs for all registered viewsets
urlpatterns += [
    path('api/v2/', include(router.urls)),
]