from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    AnimalViewSet, ProductViewSet, ReceiptViewSet, CarcassMeasurementViewSet, SlaughterPartViewSet,
    ProductCategoryViewSet, ProcessingStageViewSet, ProductTimelineEventViewSet, InventoryViewSet,
    OrderViewSet, OrderItemViewSet, ProcessingUnitViewSet, ProcessingUnitUserViewSet,
    ShopViewSet, ShopUserViewSet, UserAuditLogViewSet, ActivityViewSet,
    register_user, upload_file, health_check, server_info,
    meat_trace_list, categories_list, user_profile, processing_units_list, shops_list, production_stats,
    yield_trends, comparative_yield_trends, processing_pipeline, product_info, order_info,
    invite_user_to_processing_unit, accept_processing_unit_invitation, decline_processing_unit_invitation, leave_processing_unit,
    processing_unit_members, update_processing_unit_member, remove_processing_unit_member,
    suspend_processing_unit_member, unsuspend_processing_unit_member, processing_unit_audit_logs,
    processing_unit_member_permissions, update_processing_unit_member_permissions,
    create_processing_unit, create_shop, search_processing_units, search_shops,
    create_join_request, list_user_join_requests, review_join_request, list_unit_join_requests,
    log_activity, log_registration_activity, log_transfer_activity, CustomTokenObtainPairView,
    # Admin dashboard views
    admin_users_stats, admin_join_requests_pending, admin_suspend_user, admin_change_user_role,
    admin_supply_chain_stats, admin_pending_transfers, admin_inventory_alerts, admin_resolve_transfer, admin_traceability_product,
    admin_performance_kpis, admin_processing_stats, admin_yield_analysis, admin_create_performance_alert, admin_performance_reports,
    admin_compliance_status, admin_quality_tests, admin_schedule_audit, admin_certifications, admin_report_incident,
    admin_system_health, admin_security_logs, admin_system_performance, admin_schedule_backup, admin_system_alerts
)

app_name = 'meat_trace'

router = DefaultRouter()
router.register(r'carcass-measurements', CarcassMeasurementViewSet, basename='carcass-measurement')
router.register(r'slaughter-parts', SlaughterPartViewSet, basename='slaughter-part')
router.register(r'animals', AnimalViewSet, basename='animal')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'receipts', ReceiptViewSet, basename='receipt')
router.register(r'product-categories', ProductCategoryViewSet, basename='product-category')
router.register(r'processing-stages', ProcessingStageViewSet, basename='processing-stage')
router.register(r'product-timeline', ProductTimelineEventViewSet, basename='product-timeline')
router.register(r'inventory', InventoryViewSet, basename='inventory')
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'order-items', OrderItemViewSet, basename='order-item')
router.register(r'processing-units', ProcessingUnitViewSet, basename='processing-unit')
router.register(r'processing-unit-users', ProcessingUnitUserViewSet, basename='processing-unit-user')
router.register(r'shops', ShopViewSet, basename='shop')
router.register(r'shop-users', ShopUserViewSet, basename='shop-user')
router.register(r'audit-logs', UserAuditLogViewSet, basename='audit-log')
router.register(r'activities', ActivityViewSet, basename='activity')

urlpatterns = [
    path('api/v2/', include(router.urls)),
    path('api/v2/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
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
    # HTML view for product info
    path('api/v2/product-info/view/<str:product_id>/', product_info, name='product_info_html'),
    # API endpoint for product info
    path('api/v2/product-info/<str:product_id>/', product_info, name='product_info_api'),
    # HTML view for order info
    path('api/v2/order-info/view/<int:order_id>/', order_info, name='order_info_html'),
    # Processing unit invitation endpoints
    path('api/v2/processing-units/<int:processing_unit_id>/invite/', invite_user_to_processing_unit, name='invite_user_to_processing_unit'),
    path('api/v2/processing-unit-users/<int:membership_id>/accept/', accept_processing_unit_invitation, name='accept_processing_unit_invitation'),
    path('api/v2/processing-unit-users/<int:membership_id>/decline/', decline_processing_unit_invitation, name='decline_processing_unit_invitation'),
    path('api/v2/processing-unit-users/<int:membership_id>/leave/', leave_processing_unit, name='leave_processing_unit'),

    # Processing unit user management endpoints
    path('api/v2/processing-units/<int:processing_unit_id>/members/', processing_unit_members, name='processing_unit_members'),
    path('api/v2/processing-units/<int:processing_unit_id>/members/<int:member_id>/', update_processing_unit_member, name='update_processing_unit_member'),
    path('api/v2/processing-units/<int:processing_unit_id>/members/<int:member_id>/remove/', remove_processing_unit_member, name='remove_processing_unit_member'),
    path('api/v2/processing-units/<int:processing_unit_id>/members/<int:member_id>/suspend/', suspend_processing_unit_member, name='suspend_processing_unit_member'),
    path('api/v2/processing-units/<int:processing_unit_id>/members/<int:member_id>/unsuspend/', unsuspend_processing_unit_member, name='unsuspend_processing_unit_member'),

    # Processing unit audit and permissions endpoints
    path('api/v2/processing-units/<int:processing_unit_id>/audit-logs/', processing_unit_audit_logs, name='processing_unit_audit_logs'),
    path('api/v2/processing-units/<int:processing_unit_id>/members/<int:member_id>/permissions/', processing_unit_member_permissions, name='processing_unit_member_permissions'),
    path('api/v2/processing-units/<int:processing_unit_id>/members/<int:member_id>/permissions/update/', update_processing_unit_member_permissions, name='update_processing_unit_member_permissions'),

    # Unit creation and search endpoints
    path('api/v2/processing-units/create/', create_processing_unit, name='create_processing_unit'),
    path('api/v2/shops/create/', create_shop, name='create_shop'),
    path('api/v2/processing-units/search/', search_processing_units, name='search_processing_units'),
    path('api/v2/shops/search/', search_shops, name='search_shops'),

    # Join request endpoints
    path('api/v2/<str:unit_type>/<int:unit_id>/join-request/', create_join_request, name='create_join_request'),
    path('api/v2/join-requests/', list_user_join_requests, name='list_user_join_requests'),
    path('api/v2/join-requests/<int:request_id>/', review_join_request, name='review_join_request'),
    path('api/v2/<str:unit_type>/<int:unit_id>/join-requests/', list_unit_join_requests, name='list_unit_join_requests'),
    
    # Activity endpoints
    path('api/v2/activities/log/', log_activity, name='log_activity'),
    path('api/v2/activities/log/registration/', log_registration_activity, name='log_registration_activity'),
    path('api/v2/activities/log/transfer/', log_transfer_activity, name='log_transfer_activity'),

    # ══════════════════════════════════════════════════════════════════════════════
    # ADMIN DASHBOARD ENDPOINTS
    # ══════════════════════════════════════════════════════════════════════════════

    # User and Role Management
    path('api/v2/admin/users/stats/', admin_users_stats, name='admin_users_stats'),
    path('api/v2/admin/join-requests/pending/', admin_join_requests_pending, name='admin_join_requests_pending'),
    path('api/v2/admin/users/<int:user_id>/suspend/', admin_suspend_user, name='admin_suspend_user'),
    path('api/v2/admin/users/<int:user_id>/role/', admin_change_user_role, name='admin_change_user_role'),

    # Supply Chain Monitoring
    path('api/v2/admin/supply-chain/stats/', admin_supply_chain_stats, name='admin_supply_chain_stats'),
    path('api/v2/admin/transfers/pending/', admin_pending_transfers, name='admin_pending_transfers'),
    path('api/v2/admin/inventory/alerts/', admin_inventory_alerts, name='admin_inventory_alerts'),
    path('api/v2/admin/transfers/<int:transfer_id>/resolve/', admin_resolve_transfer, name='admin_resolve_transfer'),
    path('api/v2/admin/traceability/<int:product_id>/', admin_traceability_product, name='admin_traceability_product'),

    # Operational Performance Metrics
    path('api/v2/admin/performance/kpis/', admin_performance_kpis, name='admin_performance_kpis'),
    path('api/v2/admin/processing/stats/', admin_processing_stats, name='admin_processing_stats'),
    path('api/v2/admin/yield/analysis/', admin_yield_analysis, name='admin_yield_analysis'),
    path('api/v2/admin/alerts/performance/', admin_create_performance_alert, name='admin_create_performance_alert'),
    path('api/v2/admin/reports/performance/', admin_performance_reports, name='admin_performance_reports'),

    # Compliance and Quality Assurance
    path('api/v2/admin/compliance/status/', admin_compliance_status, name='admin_compliance_status'),
    path('api/v2/admin/quality/tests/', admin_quality_tests, name='admin_quality_tests'),
    path('api/v2/admin/audits/schedule/', admin_schedule_audit, name='admin_schedule_audit'),
    path('api/v2/admin/certifications/', admin_certifications, name='admin_certifications'),
    path('api/v2/admin/incidents/report/', admin_report_incident, name='admin_report_incident'),

    # System Health and Security
    path('api/v2/admin/system/health/', admin_system_health, name='admin_system_health'),
    path('api/v2/admin/security/logs/', admin_security_logs, name='admin_security_logs'),
    path('api/v2/admin/performance/system/', admin_system_performance, name='admin_system_performance'),
    path('api/v2/admin/backups/schedule/', admin_schedule_backup, name='admin_schedule_backup'),
    path('api/v2/admin/alerts/system/', admin_system_alerts, name='admin_system_alerts'),
]