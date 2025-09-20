from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    AnimalViewSet, ProductViewSet, ReceiptViewSet,
    ProductCategoryViewSet, ProcessingStageViewSet, ProductTimelineEventViewSet, InventoryViewSet,
    OrderViewSet, OrderItemViewSet,
    register_user, upload_file, health_check, server_info,
    meat_trace_list, categories_list, user_profile
)

app_name = 'meat_trace'

router = DefaultRouter()
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
    path('api/v1/', include(router.urls)),
    path('api/v1/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/v1/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/v1/register/', register_user, name='register'),
    path('api/v1/upload/', upload_file, name='upload_file'),
    path('api/v1/health/', health_check, name='health_check'),
    path('api/v1/info/', server_info, name='server_info'),
    path('api/v1/meattrace/', meat_trace_list, name='meat_trace_list'),
    path('api/v1/categories/', categories_list, name='categories_list'),
    path('api/v1/profile/', user_profile, name='user_profile'),
]