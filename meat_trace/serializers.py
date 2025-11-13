from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    Animal, Product, Order, Shop, SlaughterPart, CarcassMeasurement,
    ProductIngredient, UserProfile, ProcessingUnit, ProcessingUnitUser,
    ShopUser, JoinRequest, Notification, Activity, SystemAlert,
    PerformanceMetric, ComplianceAudit, Certification, SystemHealth,
    SecurityLog, TransferRequest, BackupSchedule, Sale, SaleItem,
    RejectionReason, ComplianceStatus, AuditTrail, ConfigurationHistory,
    FeatureFlag, Backup, DataExport, DataImport, GDPRRequest, DataValidation,
    ProductCategory, NotificationTemplate, NotificationChannel,
    NotificationDelivery, NotificationSchedule
)

User = get_user_model()


class SystemHealthSerializer(serializers.ModelSerializer):
    """Serializer for system health data."""
    class Meta:
        model = SystemHealth
        fields = '__all__'


class PerformanceMetricSerializer(serializers.ModelSerializer):
    """Serializer for performance metrics."""
    class Meta:
        model = PerformanceMetric
        fields = '__all__'


class SystemAlertSerializer(serializers.ModelSerializer):
    """Serializer for system alerts."""
    acknowledged_by_name = serializers.CharField(source='acknowledged_by.username', read_only=True)

    class Meta:
        model = SystemAlert
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')


class ComplianceAuditSerializer(serializers.ModelSerializer):
    """Serializer for compliance audits."""
    class Meta:
        model = ComplianceAudit
        fields = '__all__'


class CertificationSerializer(serializers.ModelSerializer):
    """Serializer for certifications."""
    class Meta:
        model = Certification
        fields = '__all__'


class SecurityLogSerializer(serializers.ModelSerializer):
    """Serializer for security logs."""
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = SecurityLog
        fields = '__all__'


class BackupScheduleSerializer(serializers.ModelSerializer):
    """Serializer for backup schedules."""
    class Meta:
        model = BackupSchedule
        fields = '__all__'


class DataExportSerializer(serializers.ModelSerializer):
    """Serializer for data exports."""
    class Meta:
        model = DataExport
        fields = '__all__'


class DataImportSerializer(serializers.ModelSerializer):
    """Serializer for data imports."""
    class Meta:
        model = DataImport
        fields = '__all__'


class GDPRRequestSerializer(serializers.ModelSerializer):
    """Serializer for GDPR requests."""
    class Meta:
        model = GDPRRequest
        fields = '__all__'


class DataValidationSerializer(serializers.ModelSerializer):
    """Serializer for data validations."""
    class Meta:
        model = DataValidation
        fields = '__all__'


class ComplianceStatusSerializer(serializers.ModelSerializer):
    """Serializer for compliance status."""
    class Meta:
        model = ComplianceStatus
        fields = '__all__'


class AuditTrailSerializer(serializers.ModelSerializer):
    """Serializer for audit trail entries."""
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = AuditTrail
        fields = '__all__'


class ConfigurationHistorySerializer(serializers.ModelSerializer):
    """Serializer for configuration history."""
    changed_by_name = serializers.CharField(source='changed_by.username', read_only=True)

    class Meta:
        model = ConfigurationHistory
        fields = '__all__'


class FeatureFlagSerializer(serializers.ModelSerializer):
    """Serializer for feature flags."""
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)

    class Meta:
        model = FeatureFlag
        fields = '__all__'


class BackupSerializer(serializers.ModelSerializer):
    """Serializer for backups."""
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    initiated_by_name = serializers.CharField(source='initiated_by.username', read_only=True)

    class Meta:
        model = Backup
        fields = '__all__'


# Monitoring-specific serializers

class SystemHealthCheckSerializer(serializers.Serializer):
    """Serializer for system health check responses."""
    timestamp = serializers.DateTimeField()
    overall_status = serializers.CharField()
    uptime = serializers.DictField()
    components = serializers.DictField()
    alerts = serializers.ListField()
    health_history = serializers.ListField(required=False)
    system_metrics = serializers.DictField(required=False)


class PerformanceMetricsSerializer(serializers.Serializer):
    """Serializer for performance monitoring responses."""
    period = serializers.CharField()
    timestamp = serializers.DateTimeField()
    metrics = serializers.DictField()
    trends = serializers.DictField()


class AlertListSerializer(serializers.Serializer):
    """Serializer for alert list responses."""
    alerts = serializers.ListField()
    pagination = serializers.DictField()
    summary = serializers.DictField()


class HistoricalDataSerializer(serializers.Serializer):
    """Serializer for historical monitoring data."""
    metric = serializers.CharField()
    period = serializers.DictField()
    data_points = serializers.ListField()
    trends = serializers.DictField()
    insights = serializers.ListField()


class AlertAcknowledgeSerializer(serializers.Serializer):
    """Serializer for alert acknowledgment."""
    notes = serializers.CharField(required=False, allow_blank=True)
    estimated_resolution_minutes = serializers.IntegerField(required=False, min_value=1)


class AlertResolveSerializer(serializers.Serializer):
    """Serializer for alert resolution."""
    resolution = serializers.CharField()
    notes = serializers.CharField(required=False, allow_blank=True)
    preventive_measures = serializers.CharField(required=False, allow_blank=True)


class DiagnosticRunSerializer(serializers.Serializer):
    """Serializer for diagnostic run requests."""
    tests = serializers.ListField(child=serializers.CharField())
    include_load_test = serializers.BooleanField(default=False)
    timeout_seconds = serializers.IntegerField(default=300, min_value=30, max_value=1800)


class DiagnosticResultSerializer(serializers.Serializer):
    """Serializer for diagnostic test results."""
    diagnostic_run_id = serializers.CharField()
    status = serializers.CharField()
    started_at = serializers.DateTimeField()
    completed_at = serializers.DateTimeField()
    duration_seconds = serializers.IntegerField()
    results = serializers.DictField()
    recommendations = serializers.ListField()
    overall_status = serializers.CharField()


class AlertConfigurationSerializer(serializers.Serializer):
    """Serializer for alert rule configuration."""
    name = serializers.CharField(max_length=200)
    component = serializers.CharField(max_length=50)
    metric = serializers.CharField(max_length=100)
    condition = serializers.DictField()
    severity = serializers.ChoiceField(choices=['low', 'medium', 'high', 'critical'])
    notification_channels = serializers.ListField(child=serializers.CharField())
    cooldown_minutes = serializers.IntegerField(default=30, min_value=1)
    auto_resolve_minutes = serializers.IntegerField(default=60, min_value=1)
    description = serializers.CharField(required=False, allow_blank=True)


class AlertConfigListSerializer(serializers.Serializer):
    """Serializer for alert configuration list."""
    alert_rules = serializers.ListField()


class RealTimeMetricsSerializer(serializers.Serializer):
    """Serializer for real-time monitoring data."""
    type = serializers.CharField()
    timestamp = serializers.DateTimeField()
    data = serializers.DictField()


# Existing serializers (keeping for compatibility)

class AnimalSerializer(serializers.ModelSerializer):
    farmer_name = serializers.CharField(source='farmer.username', read_only=True)
    processing_unit_name = serializers.CharField(source='transferred_to.name', read_only=True)
    shop_name = serializers.CharField(source='received_by_shop.name', read_only=True)

    class Meta:
        model = Animal
        fields = '__all__'


class ProductSerializer(serializers.ModelSerializer):
    animal_id = serializers.CharField(source='animal.animal_id', read_only=True)
    processing_unit_name = serializers.CharField(source='processing_unit.name', read_only=True)
    transferred_to_name = serializers.CharField(source='transferred_to.name', read_only=True)
    received_by_shop_name = serializers.CharField(source='received_by_shop.name', read_only=True)

    class Meta:
        model = Product
        fields = '__all__'


class OrderSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.username', read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)

    class Meta:
        model = Order
        fields = '__all__'


class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = '__all__'


class SlaughterPartSerializer(serializers.ModelSerializer):
    animal_id = serializers.CharField(source='animal.animal_id', read_only=True)

    class Meta:
        model = SlaughterPart
        fields = '__all__'


class CarcassMeasurementSerializer(serializers.ModelSerializer):
    animal_id = serializers.CharField(source='animal.animal_id', read_only=True)

    class Meta:
        model = CarcassMeasurement
        fields = '__all__'


class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = '__all__'


class ProductIngredientSerializer(serializers.ModelSerializer):
    slaughter_part_type = serializers.CharField(source='slaughter_part.part_type', read_only=True)

    class Meta:
        model = ProductIngredient
        fields = '__all__'


class UserProfileSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    processing_unit_name = serializers.CharField(source='processing_unit.name', read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)

    class Meta:
        model = UserProfile
        fields = '__all__'


class ProcessingUnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessingUnit
        fields = '__all__'


class ProcessingUnitUserSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    processing_unit_name = serializers.CharField(source='processing_unit.name', read_only=True)

    class Meta:
        model = ProcessingUnitUser
        fields = '__all__'


class ShopUserSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)

    class Meta:
        model = ShopUser
        fields = '__all__'


class JoinRequestSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    processing_unit_name = serializers.CharField(source='processing_unit.name', read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)

    class Meta:
        model = JoinRequest
        fields = '__all__'


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'


class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = '__all__'


class NotificationChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationChannel
        fields = '__all__'


class NotificationDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationDelivery
        fields = '__all__'


class NotificationScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationSchedule
        fields = '__all__'


class ActivitySerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Activity
        fields = '__all__'


class TransferRequestSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.CharField(source='requested_by.username', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.username', read_only=True)
    from_processing_unit_name = serializers.CharField(source='from_processing_unit.name', read_only=True)
    to_processing_unit_name = serializers.CharField(source='to_processing_unit.name', read_only=True)

    class Meta:
        model = TransferRequest
        fields = '__all__'


class SaleSerializer(serializers.ModelSerializer):
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    sold_by_name = serializers.CharField(source='sold_by.username', read_only=True)

    class Meta:
        model = Sale
        fields = '__all__'


class SaleItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = SaleItem
        fields = '__all__'


class RejectionReasonSerializer(serializers.ModelSerializer):
    rejected_by_name = serializers.CharField(source='rejected_by.username', read_only=True)
    animal_id = serializers.CharField(source='animal.animal_id', read_only=True)
    processing_unit_name = serializers.CharField(source='processing_unit.name', read_only=True)

    class Meta:
        model = RejectionReason
        fields = '__all__'


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN DASHBOARD SERIALIZERS
# ══════════════════════════════════════════════════════════════════════════════

class AdminDashboardStatsSerializer(serializers.Serializer):
    """Serializer for admin dashboard overview statistics"""
    total_users = serializers.IntegerField()
    total_farmers = serializers.IntegerField()
    total_processors = serializers.IntegerField()
    total_shop_owners = serializers.IntegerField()
    total_admins = serializers.IntegerField()

    total_processing_units = serializers.IntegerField()
    total_shops = serializers.IntegerField()
    active_processing_units = serializers.IntegerField()
    active_shops = serializers.IntegerField()

    total_animals = serializers.IntegerField()
    total_products = serializers.IntegerField()
    total_orders = serializers.IntegerField()
    total_sales = serializers.IntegerField()

    recent_animals_count = serializers.IntegerField()
    recent_products_count = serializers.IntegerField()
    recent_orders_count = serializers.IntegerField()
    recent_activities_count = serializers.IntegerField()

    system_health_status = serializers.CharField()
    active_alerts_count = serializers.IntegerField()


class AdminUserListSerializer(serializers.ModelSerializer):
    """Serializer for admin user management list view"""
    profile_role = serializers.CharField(source='profile.role', read_only=True)
    profile_processing_unit = serializers.CharField(source='profile.processing_unit.name', read_only=True)
    profile_shop = serializers.CharField(source='profile.shop.name', read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    date_joined = serializers.DateTimeField(read_only=True)
    last_login = serializers.DateTimeField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'profile_role', 'profile_processing_unit', 'profile_shop',
            'is_active', 'date_joined', 'last_login'
        ]


class AdminUserDetailSerializer(serializers.ModelSerializer):
    """Serializer for admin user management detail view"""
    profile = UserProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_active', 'is_staff', 'is_superuser', 'date_joined', 'last_login',
            'profile'
        ]


class AdminUserCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating users in admin panel"""
    password = serializers.CharField(write_only=True, required=False)
    role = serializers.ChoiceField(choices=[], write_only=True, required=False)  # Choices set in __init__
    processing_unit_id = serializers.IntegerField(write_only=True, required=False)
    shop_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'password', 'is_active', 'role', 'processing_unit_id', 'shop_id'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].choices = UserProfile.ROLE_CHOICES

    def create(self, validated_data):
        role = validated_data.pop('role', None)
        processing_unit_id = validated_data.pop('processing_unit_id', None)
        shop_id = validated_data.pop('shop_id', None)
        password = validated_data.pop('password', None)

        user = User.objects.create_user(**validated_data)
        if password:
            user.set_password(password)
            user.save()

        # Create or update profile
        profile_data = {}
        if role:
            profile_data['role'] = role
        if processing_unit_id:
            try:
                profile_data['processing_unit'] = ProcessingUnit.objects.get(id=processing_unit_id)
            except ProcessingUnit.DoesNotExist:
                pass
        if shop_id:
            try:
                profile_data['shop'] = Shop.objects.get(id=shop_id)
            except Shop.DoesNotExist:
                pass

        if profile_data:
            UserProfile.objects.update_or_create(user=user, defaults=profile_data)

        return user

    def update(self, instance, validated_data):
        role = validated_data.pop('role', None)
        processing_unit_id = validated_data.pop('processing_unit_id', None)
        shop_id = validated_data.pop('shop_id', None)
        password = validated_data.pop('password', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()

        # Update profile
        profile_data = {}
        if role:
            profile_data['role'] = role
        if processing_unit_id:
            try:
                profile_data['processing_unit'] = ProcessingUnit.objects.get(id=processing_unit_id)
            except ProcessingUnit.DoesNotExist:
                pass
        if shop_id:
            try:
                profile_data['shop'] = Shop.objects.get(id=shop_id)
            except Shop.DoesNotExist:
                pass

        if profile_data:
            UserProfile.objects.update_or_create(user=instance, defaults=profile_data)

        return instance


class AdminProcessingUnitSerializer(serializers.ModelSerializer):
    """Serializer for admin processing unit management"""
    member_count = serializers.SerializerMethodField()
    active_members_count = serializers.SerializerMethodField()
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = ProcessingUnit
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

    def get_member_count(self, obj):
        return obj.members.count()

    def get_active_members_count(self, obj):
        return obj.members.filter(is_active=True).count()

    def get_product_count(self, obj):
        return obj.products.count()


class AdminShopSerializer(serializers.ModelSerializer):
    """Serializer for admin shop management"""
    member_count = serializers.SerializerMethodField()
    active_members_count = serializers.SerializerMethodField()
    inventory_count = serializers.SerializerMethodField()
    order_count = serializers.SerializerMethodField()
    sale_count = serializers.SerializerMethodField()

    class Meta:
        model = Shop
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

    def get_member_count(self, obj):
        return obj.members.count()

    def get_active_members_count(self, obj):
        return obj.members.filter(is_active=True).count()

    def get_inventory_count(self, obj):
        return obj.inventory.count()

    def get_order_count(self, obj):
        return obj.orders.count()

    def get_sale_count(self, obj):
        return obj.sales.count()


class AdminAnimalOverviewSerializer(serializers.ModelSerializer):
    """Serializer for admin animal traceability overview"""
    farmer_name = serializers.CharField(source='farmer.username', read_only=True)
    processing_unit_name = serializers.CharField(source='transferred_to.name', read_only=True)
    lifecycle_status = serializers.ReadOnlyField()
    has_rejections = serializers.SerializerMethodField()
    has_appeals = serializers.SerializerMethodField()

    class Meta:
        model = Animal
        fields = [
            'id', 'animal_id', 'animal_name', 'species', 'age', 'live_weight',
            'farmer_name', 'processing_unit_name', 'slaughtered', 'slaughtered_at',
            'transferred_at', 'lifecycle_status', 'has_rejections', 'has_appeals',
            'created_at'
        ]

    def get_has_rejections(self, obj):
        return obj.rejection_reasons.exists()

    def get_has_appeals(self, obj):
        return obj.appeal_status is not None


class AdminProductOverviewSerializer(serializers.ModelSerializer):
    """Serializer for admin product traceability overview"""
    animal_id = serializers.CharField(source='animal.animal_id', read_only=True)
    processing_unit_name = serializers.CharField(source='processing_unit.name', read_only=True)
    transferred_to_name = serializers.CharField(source='transferred_to.name', read_only=True)
    received_by_shop_name = serializers.CharField(source='received_by_shop.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'batch_number', 'product_type', 'quantity', 'weight',
            'animal_id', 'processing_unit_name', 'transferred_to_name',
            'received_by_shop_name', 'category_name', 'created_at', 'transferred_at'
        ]


class AdminAnalyticsSerializer(serializers.Serializer):
    """Serializer for admin analytics data"""
    period = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()

    # User metrics
    new_users_count = serializers.IntegerField()
    active_users_count = serializers.IntegerField()

    # Entity metrics
    new_animals_count = serializers.IntegerField()
    new_products_count = serializers.IntegerField()
    new_orders_count = serializers.IntegerField()
    new_sales_count = serializers.IntegerField()

    # Processing metrics
    processing_efficiency = serializers.DecimalField(max_digits=5, decimal_places=2)
    transfer_success_rate = serializers.DecimalField(max_digits=5, decimal_places=2)

    # Financial metrics
    total_sales_value = serializers.DecimalField(max_digits=10, decimal_places=2)
    average_order_value = serializers.DecimalField(max_digits=10, decimal_places=2)

    # System metrics
    system_uptime = serializers.DecimalField(max_digits=5, decimal_places=2)
    error_rate = serializers.DecimalField(max_digits=5, decimal_places=2)


class AdminRecentActivitySerializer(serializers.Serializer):
    """Serializer for recent activity feed in admin dashboard"""
    activities = serializers.ListField()
    total_count = serializers.IntegerField()
    pagination = serializers.DictField()
