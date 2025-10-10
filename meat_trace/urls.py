from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    AnimalViewSet, ProductViewSet, ReceiptViewSet, CarcassMeasurementViewSet,
    ProductCategoryViewSet, ProcessingStageViewSet, ProductTimelineEventViewSet, InventoryViewSet,
    OrderViewSet, OrderItemViewSet,
    register_user, upload_file, health_check, server_info,
    meat_trace_list, categories_list, user_profile, processing_units_list, shops_list, production_stats,
    yield_trends, comparative_yield_trends, processing_pipeline, product_info
)

app_name = 'meat_trace'

router = DefaultRouter()
router.register(r'carcass-measurements', CarcassMeasurementViewSet, basename='carcass-measurement')
router.register(r'animals', AnimalViewSet, basename='animal')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'receipts', ReceiptViewSet, basename='receipt')
router.register(r'product-categories', ProductCategoryViewSet, basename='product-category')
router.register(r'processing-stages', ProcessingStageViewSet, basename='processing-stage')
router.register(r'product-timeline', ProductTimelineEventViewSet, basename='product-timeline')
router.register(r'inventory', InventoryViewSet, basename='inventory')
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'order-items', OrderItemViewSet, basename='order-item')

urlpatterns = [
    path('api/v2/', include(router.urls)),
    path('api/v2/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/v2/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/v2/register/', register_user, name='register'),
    path('api/v2/upload/', upload_file, name='upload_file'),
    path('api/v2/health/', health_check, name='health_check'),
    path('api/v2/info/', server_info, name='server_info'),
    path('api/v2/meattrace/', meat_trace_list, name='meat_trace_list'),
    path('api/v2/categories/', categories_list, name='categories_list'),
    path('api/v2/profile/', user_profile, name='user_profile'),
    path('api/v2/processing-units/', processing_units_list, name='processing_units_list'),
    path('api/v2/shops/', shops_list, name='shops_list'),
    path('api/v2/production-stats/', production_stats, name='production_stats'),
    path('api/v2/yield-trends/', yield_trends, name='yield_trends'),
    path('api/v2/yield-trends/comparative/', comparative_yield_trends, name='comparative_yield_trends'),
    path('api/v2/processing-pipeline/', processing_pipeline, name='processing_pipeline'),
    path('api/product-info/<str:product_id>/', product_info, name='product_info'),
]