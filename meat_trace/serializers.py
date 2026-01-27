
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import transaction
from .models import (
    User, UserProfile, UserAuditLog, Animal, SlaughterPart, 
    ProductIngredient, CarcassMeasurement, Product, Inventory, 
    ProcessingUnit, ProcessingUnitUser, Shop, ShopUser, Order, OrderItem,
    ComplianceAudit, Certification, RegistrationApplication, ApprovalWorkflow,
    JoinRequest, Notification, Activity, SystemAlert, PerformanceMetric, 
    SystemHealth, SecurityLog, TransferRequest, BackupSchedule, Sale, SaleItem,
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
    """Serializer for compliance audits with computed fields."""
    entity_name = serializers.SerializerMethodField()
    auditor_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ComplianceAudit
        fields = '__all__'
    
    def get_entity_name(self, obj):
        """Get the name of the audited entity."""
        if obj.processing_unit:
            return obj.processing_unit.name
        elif obj.shop:
            return obj.shop.name
        elif obj.abbatoir:
            return obj.abbatoir.username
        return 'Unknown Entity'
    
    def get_auditor_name(self, obj):
        """Get the auditor's username."""
        return obj.auditor.username if obj.auditor else 'Unassigned'


class CertificationSerializer(serializers.ModelSerializer):
    """Serializer for certifications with computed fields."""
    entity_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Certification
        fields = '__all__'
    
    def get_entity_name(self, obj):
        """Get the name of the certified entity."""
        if obj.processing_unit:
            return obj.processing_unit.name
        elif obj.shop:
            return obj.shop.name
        elif obj.abbatoir:
            return obj.abbatoir.username
        return 'Unknown Entity'


class RegistrationApplicationSerializer(serializers.ModelSerializer):
    """Serializer for registration applications."""
    class Meta:
        model = RegistrationApplication
        fields = '__all__'


class ApprovalWorkflowSerializer(serializers.ModelSerializer):
    """Serializer for approval workflows."""
    class Meta:
        model = ApprovalWorkflow
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
# NOTE: Order matters to avoid circular imports - define nested serializers first

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

    def to_internal_value(self, data):
        """
        Extract weight values from nested measurements JSON and populate individual fields.
        Frontend sends: {"measurements": {"whole_carcass_weight": {"value": 32.6, "unit": "kg"}}}
        We need to extract these values into individual model fields.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Make a mutable copy of data
        mutable_data = data.copy() if hasattr(data, 'copy') else dict(data)
        
        measurements = mutable_data.get('measurements', {})
        
        if measurements:
            logger.info(f"[CARCASS_SERIALIZER] Extracting weights from measurements: {measurements}")
            
            # Weight fields that can be extracted from measurements JSON
            weight_fields = ['head_weight', 'torso_weight', 'left_carcass_weight',
                            'right_carcass_weight', 'feet_weight', 'whole_carcass_weight', 'organs_weight']
            
            for field_name in weight_fields:
                if field_name in measurements and mutable_data.get(field_name) is None:
                    measurement_value = measurements[field_name]
                    # Handle both formats: {"value": 32.6, "unit": "kg"} or just 32.6
                    if isinstance(measurement_value, dict):
                        value = measurement_value.get('value')
                    else:
                        value = measurement_value
                    
                    if value is not None:
                        mutable_data[field_name] = value
                        logger.info(f"[CARCASS_SERIALIZER] Extracted {field_name} = {value}")
        
        return super().to_internal_value(mutable_data)

    def validate(self, attrs):
        """
        Validate carcass measurement data based on carcass type.
        This ensures proper validation errors (400) instead of server errors (500).
        """
        import logging
        logger = logging.getLogger(__name__)
        
        carcass_type = attrs.get('carcass_type', 'whole')
        logger.info(f"[CARCASS_SERIALIZER] Validating carcass_type: {carcass_type}")
        logger.info(f"[CARCASS_SERIALIZER] Attrs after extraction: {attrs}")
        
        # Validate required fields based on carcass_type
        if carcass_type == 'whole':
            whole_carcass_weight = attrs.get('whole_carcass_weight')
            if whole_carcass_weight is None:
                raise serializers.ValidationError({
                    'whole_carcass_weight': 'For whole carcass, whole_carcass_weight is required.'
                })
        elif carcass_type == 'split':
            left_carcass_weight = attrs.get('left_carcass_weight')
            right_carcass_weight = attrs.get('right_carcass_weight')
            
            errors = {}
            if left_carcass_weight is None:
                errors['left_carcass_weight'] = 'For split carcass, left_carcass_weight is required.'
            if right_carcass_weight is None:
                errors['right_carcass_weight'] = 'For split carcass, right_carcass_weight is required.'
            
            if errors:
                raise serializers.ValidationError(errors)
        
        # Validate all weights are positive
        weight_fields = ['head_weight', 'torso_weight', 'left_carcass_weight',
                        'right_carcass_weight', 'feet_weight', 'whole_carcass_weight', 'organs_weight']
        for field_name in weight_fields:
            weight = attrs.get(field_name)
            if weight is not None:
                if weight <= 0:
                    raise serializers.ValidationError({
                        field_name: f'{field_name.replace("_", " ").title()} must be positive.'
                    })
                # Check for unrealistic weights
                if weight > 2000:
                    raise serializers.ValidationError({
                        field_name: f'{field_name.replace("_", " ").title()} seems unusually large. Please verify the measurement.'
                    })
        
        return attrs


class AnimalSerializer(serializers.ModelSerializer):
    abbatoir_name = serializers.CharField(source='abbatoir.username', read_only=True)
    farmer_name = serializers.CharField(source='abbatoir.username', read_only=True)
>>>>>>> aa57a1f (Implement weight-based selling and inventory management)
    processing_unit_name = serializers.CharField(source='transferred_to.name', read_only=True)
    shop_name = serializers.CharField(source='received_by_shop.name', read_only=True)
    # FIX: Include nested carcass_measurement and slaughter_parts for split carcass detection
    carcass_measurement = CarcassMeasurementSerializer(read_only=True)
    slaughter_parts = SlaughterPartSerializer(many=True, read_only=True)
    
    # Add lifecycle status properties as read-only fields
    lifecycle_status = serializers.ReadOnlyField()
    is_healthy = serializers.ReadOnlyField()
    is_slaughtered_status = serializers.ReadOnlyField()
    is_transferred_status = serializers.ReadOnlyField()
    is_semi_transferred_status = serializers.ReadOnlyField()

    class Meta:
        model = Animal
        fields = '__all__'
        read_only_fields = ['abbatoir', 'animal_id', 'created_at', 'slaughtered_at',
                           'transferred_at', 'received_at', 'rejected_at',
                           'appealed_at', 'appeal_resolved_at']


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
    # Add fields with names expected by Flutter app
    user = serializers.IntegerField(source='user_id', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    processing_unit = serializers.IntegerField(source='processing_unit_id', read_only=True)
    processing_unit_name = serializers.CharField(source='processing_unit.name', read_only=True)
    invited_by = serializers.IntegerField(source='invited_by_id', read_only=True, allow_null=True)
    invited_by_username = serializers.CharField(source='invited_by.username', read_only=True, allow_null=True)

    class Meta:
        model = ProcessingUnitUser
        fields = [
            'id', 'user', 'user_username', 'user_email',
            'processing_unit', 'processing_unit_name',
            'role', 'permissions', 'granular_permissions',
            'invited_by', 'invited_by_username', 'invited_at',
            'joined_at', 'is_active', 'is_suspended', 'suspension_reason',
            'suspension_date', 'last_active'
        ]


class ShopUserSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)

    class Meta:
        model = ShopUser
        fields = '__all__'


class JoinRequestSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    processing_unit_name = serializers.CharField(source='processing_unit.name', read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    
    # Add these fields for backward compatibility with Flutter app
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)

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


class SaleItemWriteSerializer(serializers.ModelSerializer):
    """Write-only serializer used to accept nested sale item payloads."""
    class Meta:
        model = SaleItem
        fields = ['product', 'quantity', 'weight', 'weight_unit', 'unit_price', 'subtotal']



class SaleSerializer(serializers.ModelSerializer):
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    sold_by_name = serializers.CharField(source='sold_by.username', read_only=True)

    # Accept nested items for creation under this write-only field
    # Frontend sends 'items' in the request payload
    items = SaleItemWriteSerializer(many=True, write_only=True, required=False)

    class Meta:
        model = Sale
        fields = '__all__'

    def to_representation(self, instance):
        """Include nested sale items in serialized output."""
        data = super().to_representation(instance)
        # Attach items using SaleItemSerializer if available
        try:
            data['items'] = SaleItemSerializer(instance.items.all(), many=True).data
        except Exception:
            data['items'] = []
        return data

    def create(self, validated_data):
        """Create Sale and nested SaleItem records transactionally.

        Expects frontend to send items under the key 'items'.
        """
        # Extract items from validated data
        items_data = validated_data.pop('items', [])

        if not items_data:
            # Allow creating sales without items but warn (keeps compatibility)
            # If you want to enforce items, raise a ValidationError here.
            pass

        with transaction.atomic():
            sale = Sale.objects.create(**validated_data)

            for item in items_data:
                # item is a dict containing product (id or instance), quantity, unit_price, subtotal
                SaleItem.objects.create(sale=sale, **item)

        return sale


class SaleItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    batch_number = serializers.CharField(source='product.batch_number', read_only=True)

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
    total_abbatoirs = serializers.IntegerField()
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
    profile_phone = serializers.CharField(source='profile.phone', read_only=True)
    profile_address = serializers.CharField(source='profile.address', read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    date_joined = serializers.DateTimeField(read_only=True)
    last_login = serializers.DateTimeField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'profile_role', 'profile_processing_unit', 'profile_shop',
            'profile_phone', 'profile_address',
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
    # Profile fields for phone and address (location)
    phone = serializers.CharField(write_only=True, required=False, allow_blank=True)
    address = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'password', 'is_active', 'role', 'processing_unit_id', 'shop_id',
            'phone', 'address'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].choices = UserProfile.ROLE_CHOICES

    def create(self, validated_data):
        role = validated_data.pop('role', 'Abbatoir')  # Default to Abbatoir
        processing_unit_id = validated_data.pop('processing_unit_id', None)
        shop_id = validated_data.pop('shop_id', None)
        password = validated_data.pop('password', None)
        phone = validated_data.pop('phone', '')
        address = validated_data.pop('address', '')
        
        # Create user with password
        user = User.objects.create_user(
            username=validated_data.get('username'),
            email=validated_data.get('email', ''),
            password=password if password else 'changeme123',  # Default password if not provided
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
        )
        
        # Set additional user fields
        if validated_data.get('is_active') is not None:
            user.is_active = validated_data.get('is_active')
            user.save()

        # Create or update profile with role, phone, and address
        profile_data = {
            'role': role,
            'phone': phone,
            'address': address,
        }
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

        # This will trigger geocoding via the model's save() method
        UserProfile.objects.update_or_create(user=user, defaults=profile_data)

        # If role is Processor and processing_unit_id is provided, create ProcessingUnitUser
        if role == 'Processor' and processing_unit_id:
            try:
                processing_unit = ProcessingUnit.objects.get(id=processing_unit_id)
                from .models import ProcessingUnitUser
                ProcessingUnitUser.objects.get_or_create(
                    user=user,
                    processing_unit=processing_unit,
                    defaults={'is_active': True, 'is_suspended': False}
                )
            except ProcessingUnit.DoesNotExist:
                pass

        # If role is ShopOwner and shop_id is provided, create ShopUser
        if role == 'ShopOwner' and shop_id:
            try:
                shop = Shop.objects.get(id=shop_id)
                from .models import ShopUser
                ShopUser.objects.get_or_create(
                    user=user,
                    shop=shop,
                    defaults={'is_active': True}
                )
            except Shop.DoesNotExist:
                pass

        return user

    def update(self, instance, validated_data):
        role = validated_data.pop('role', None)
        processing_unit_id = validated_data.pop('processing_unit_id', None)
        shop_id = validated_data.pop('shop_id', None)
        password = validated_data.pop('password', None)
        phone = validated_data.pop('phone', None)
        address = validated_data.pop('address', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()

        # Update profile
        profile_data = {}
        if role:
            profile_data['role'] = role
        if phone is not None:
            profile_data['phone'] = phone
        if address is not None:
            profile_data['address'] = address
            # Clear existing coordinates so geocoding runs again
            profile_data['latitude'] = None
            profile_data['longitude'] = None
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
            # Get or create profile, then save to trigger geocoding
            profile, created = UserProfile.objects.get_or_create(user=instance)
            for key, value in profile_data.items():
                setattr(profile, key, value)
            profile.save()  # This triggers geocoding

        # If role is Processor and processing_unit_id is provided, ensure ProcessingUnitUser exists
        if role == 'Processor' and processing_unit_id:
            try:
                processing_unit = ProcessingUnit.objects.get(id=processing_unit_id)
                from .models import ProcessingUnitUser
                ProcessingUnitUser.objects.get_or_create(
                    user=instance,
                    processing_unit=processing_unit,
                    defaults={'is_active': True, 'is_suspended': False}
                )
            except ProcessingUnit.DoesNotExist:
                pass

        # If role is ShopOwner and shop_id is provided, ensure ShopUser exists
        if role == 'ShopOwner' and shop_id:
            try:
                shop = Shop.objects.get(id=shop_id)
                from .models import ShopUser
                ShopUser.objects.get_or_create(
                    user=instance,
                    shop=shop,
                    defaults={'is_active': True}
                )
            except Shop.DoesNotExist:
                pass

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
    abbatoir_name = serializers.CharField(source='abbatoir.username', read_only=True)
    farmer_name = serializers.CharField(source='abbatoir.username', read_only=True)
>>>>>>> aa57a1f (Implement weight-based selling and inventory management)
    processing_unit_name = serializers.CharField(source='transferred_to.name', read_only=True)
    lifecycle_status = serializers.ReadOnlyField()
    has_rejections = serializers.SerializerMethodField()
    has_appeals = serializers.SerializerMethodField()

    class Meta:
        model = Animal
        fields = [
            'id', 'animal_id', 'animal_name', 'species', 'age', 'live_weight',
            'abbatoir_name', 'processing_unit_name', 'slaughtered', 'slaughtered_at',
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


class ReceiptSerializer(serializers.ModelSerializer):
    """Serializer for product receipts"""
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_type = serializers.CharField(source='product.product_type', read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)

    class Meta:
        from .models import Receipt
        model = Receipt
        fields = ['id', 'shop', 'shop_name', 'product', 'product_name', 'product_type', 
                  'received_quantity', 'received_weight', 'weight_unit', 'received_at']
        read_only_fields = ['received_at']


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN CRUD SERIALIZERS - For creating/updating entities at any traceability point
# ══════════════════════════════════════════════════════════════════════════════

class AdminAnimalCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for admin to create/update animals at any traceability point"""
    abbatoir_id = serializers.IntegerField(write_only=True)
    processing_unit_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    # Read-only fields for response
    abbatoir_name = serializers.CharField(source='abbatoir.username', read_only=True)
    farmer_name = serializers.CharField(source='abbatoir.username', read_only=True)
>>>>>>> aa57a1f (Implement weight-based selling and inventory management)
    processing_unit_name = serializers.CharField(source='transferred_to.name', read_only=True)
    lifecycle_status = serializers.ReadOnlyField()

    class Meta:
        model = Animal
        fields = [
            'id', 'animal_id', 'animal_name', 'species', 'breed', 'age', 'gender',
            'live_weight', 'remaining_weight', 'notes', 'health_status',
            'slaughtered', 'slaughtered_at', 'processed',
            'abbatoir_id', 'abbatoir_name', 'processing_unit_id', 'processing_unit_name',
            'lifecycle_status', 'created_at'
        ]
        read_only_fields = ['animal_id', 'created_at', 'lifecycle_status']

    def validate_abbatoir_id(self, value):
        try:
            user = User.objects.get(id=value)
            # Verify user is a abbatoir
            if hasattr(user, 'profile') and user.profile.role != 'Abbatoir':
                raise serializers.ValidationError("Selected user is not a abbatoir.")
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("Abbatoir not found.")

    def validate_processing_unit_id(self, value):
        if value is None:
            return value
        try:
            ProcessingUnit.objects.get(id=value)
            return value
        except ProcessingUnit.DoesNotExist:
            raise serializers.ValidationError("Processing unit not found.")

    def create(self, validated_data):
        from django.utils import timezone
        abbatoir_id = validated_data.pop('abbatoir_id')
        processing_unit_id = validated_data.pop('processing_unit_id', None)
        
        abbatoir = User.objects.get(id=abbatoir_id)
        abbatoir = User.objects.get(id=farmer_id)
>>>>>>> aa57a1f (Implement weight-based selling and inventory management)
        validated_data['abbatoir'] = abbatoir
        
        if processing_unit_id:
            processing_unit = ProcessingUnit.objects.get(id=processing_unit_id)
            validated_data['transferred_to'] = processing_unit
            validated_data['transferred_at'] = timezone.now()
        
        return super().create(validated_data)

    def update(self, instance, validated_data):
        from django.utils import timezone
        abbatoir_id = validated_data.pop('abbatoir_id', None)
        processing_unit_id = validated_data.pop('processing_unit_id', None)
        
        if abbatoir_id:
            instance.abbatoir = User.objects.get(id=abbatoir_id)
        if farmer_id:
            instance.abbatoir = User.objects.get(id=farmer_id)
>>>>>>> aa57a1f (Implement weight-based selling and inventory management)
        
        if processing_unit_id is not None:
            if processing_unit_id:
                instance.transferred_to = ProcessingUnit.objects.get(id=processing_unit_id)
                if not instance.transferred_at:
                    instance.transferred_at = timezone.now()
            else:
                instance.transferred_to = None
                instance.transferred_at = None
        
        return super().update(instance, validated_data)


class AdminProductCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for admin to create/update products at any traceability point"""
    processing_unit_id = serializers.IntegerField(write_only=True)
    animal_id = serializers.IntegerField(write_only=True)
    slaughter_part_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    category_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    shop_id = serializers.IntegerField(write_only=True, required=False, allow_null=True,
                                        help_text="Assign product directly to a shop")
    
    # Read-only fields for response
    animal_id_display = serializers.CharField(source='animal.animal_id', read_only=True)
    processing_unit_name = serializers.CharField(source='processing_unit.name', read_only=True)
    transferred_to_name = serializers.CharField(source='transferred_to.name', read_only=True)
    received_by_shop_name = serializers.CharField(source='received_by_shop.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    slaughter_part_type = serializers.CharField(source='slaughter_part.part_type', read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'batch_number', 'product_type', 'description',
            'quantity', 'weight', 'weight_unit', 'price', 'manufacturer',
            'processing_unit_id', 'processing_unit_name',
            'animal_id', 'animal_id_display',
            'slaughter_part_id', 'slaughter_part_type',
            'category_id', 'category_name',
            'shop_id', 'transferred_to_name', 'received_by_shop_name',
            'transferred_at', 'received_at', 'quantity_received',
            'created_at'
        ]
        read_only_fields = ['created_at']

    def validate_processing_unit_id(self, value):
        try:
            ProcessingUnit.objects.get(id=value)
            return value
        except ProcessingUnit.DoesNotExist:
            raise serializers.ValidationError("Processing unit not found.")

    def validate_animal_id(self, value):
        try:
            Animal.objects.get(id=value)
            return value
        except Animal.DoesNotExist:
            raise serializers.ValidationError("Animal not found.")

    def validate_slaughter_part_id(self, value):
        if value is None:
            return value
        try:
            SlaughterPart.objects.get(id=value)
            return value
        except SlaughterPart.DoesNotExist:
            raise serializers.ValidationError("Slaughter part not found.")

    def validate_category_id(self, value):
        if value is None:
            return value
        try:
            ProductCategory.objects.get(id=value)
            return value
        except ProductCategory.DoesNotExist:
            raise serializers.ValidationError("Product category not found.")

    def validate_shop_id(self, value):
        if value is None:
            return value
        try:
            Shop.objects.get(id=value)
            return value
        except Shop.DoesNotExist:
            raise serializers.ValidationError("Shop not found.")

    def create(self, validated_data):
        from django.utils import timezone
        processing_unit_id = validated_data.pop('processing_unit_id')
        animal_id = validated_data.pop('animal_id')
        slaughter_part_id = validated_data.pop('slaughter_part_id', None)
        category_id = validated_data.pop('category_id', None)
        shop_id = validated_data.pop('shop_id', None)
        
        validated_data['processing_unit'] = ProcessingUnit.objects.get(id=processing_unit_id)
        validated_data['animal'] = Animal.objects.get(id=animal_id)
        
        if slaughter_part_id:
            validated_data['slaughter_part'] = SlaughterPart.objects.get(id=slaughter_part_id)
        
        if category_id:
            validated_data['category'] = ProductCategory.objects.get(id=category_id)
        
        # If shop_id is provided, assign product to shop
        if shop_id:
            shop = Shop.objects.get(id=shop_id)
            validated_data['transferred_to'] = shop
            validated_data['received_by_shop'] = shop
            validated_data['transferred_at'] = timezone.now()
            validated_data['received_at'] = timezone.now()
            if 'quantity_received' not in validated_data or not validated_data['quantity_received']:
                validated_data['quantity_received'] = validated_data.get('quantity', 0)
        
        return super().create(validated_data)

    def update(self, instance, validated_data):
        from django.utils import timezone
        processing_unit_id = validated_data.pop('processing_unit_id', None)
        animal_id = validated_data.pop('animal_id', None)
        slaughter_part_id = validated_data.pop('slaughter_part_id', None)
        category_id = validated_data.pop('category_id', None)
        shop_id = validated_data.pop('shop_id', None)
        
        if processing_unit_id:
            instance.processing_unit = ProcessingUnit.objects.get(id=processing_unit_id)
        
        if animal_id:
            instance.animal = Animal.objects.get(id=animal_id)
        
        if slaughter_part_id is not None:
            if slaughter_part_id:
                instance.slaughter_part = SlaughterPart.objects.get(id=slaughter_part_id)
            else:
                instance.slaughter_part = None
        
        if category_id is not None:
            if category_id:
                instance.category = ProductCategory.objects.get(id=category_id)
            else:
                instance.category = None
        
        # Handle shop assignment
        if shop_id is not None:
            if shop_id:
                shop = Shop.objects.get(id=shop_id)
                instance.transferred_to = shop
                instance.received_by_shop = shop
                if not instance.transferred_at:
                    instance.transferred_at = timezone.now()
                if not instance.received_at:
                    instance.received_at = timezone.now()
            else:
                instance.transferred_to = None
                instance.received_by_shop = None
                instance.transferred_at = None
                instance.received_at = None
        
        return super().update(instance, validated_data)


class AdminSlaughterPartCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for admin to create/update slaughter parts"""
    animal_id = serializers.IntegerField(write_only=True)
    processing_unit_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    # Read-only fields for response
    animal_id_display = serializers.CharField(source='animal.animal_id', read_only=True)
    animal_species = serializers.CharField(source='animal.species', read_only=True)
    processing_unit_name = serializers.CharField(source='transferred_to.name', read_only=True)

    class Meta:
        model = SlaughterPart
        fields = [
            'id', 'part_id', 'part_type', 'weight', 'remaining_weight', 'weight_unit',
            'description', 'used_in_product', 'is_selected_for_transfer',
            'animal_id', 'animal_id_display', 'animal_species',
            'processing_unit_id', 'processing_unit_name',
            'transferred_at', 'received_at', 'created_at'
        ]
        read_only_fields = ['part_id', 'created_at']

    def validate_animal_id(self, value):
        try:
            animal = Animal.objects.get(id=value)
            # Verify animal is slaughtered
            if not animal.slaughtered:
                raise serializers.ValidationError("Animal must be slaughtered before adding parts.")
            return value
        except Animal.DoesNotExist:
            raise serializers.ValidationError("Animal not found.")

    def validate_processing_unit_id(self, value):
        if value is None:
            return value
        try:
            ProcessingUnit.objects.get(id=value)
            return value
        except ProcessingUnit.DoesNotExist:
            raise serializers.ValidationError("Processing unit not found.")

    def create(self, validated_data):
        from django.utils import timezone
        animal_id = validated_data.pop('animal_id')
        processing_unit_id = validated_data.pop('processing_unit_id', None)
        
        validated_data['animal'] = Animal.objects.get(id=animal_id)
        
        if processing_unit_id:
            validated_data['transferred_to'] = ProcessingUnit.objects.get(id=processing_unit_id)
            validated_data['transferred_at'] = timezone.now()
        
        return super().create(validated_data)

    def update(self, instance, validated_data):
        from django.utils import timezone
        animal_id = validated_data.pop('animal_id', None)
        processing_unit_id = validated_data.pop('processing_unit_id', None)
        
        if animal_id:
            instance.animal = Animal.objects.get(id=animal_id)
        
        if processing_unit_id is not None:
            if processing_unit_id:
                instance.transferred_to = ProcessingUnit.objects.get(id=processing_unit_id)
                if not instance.transferred_at:
                    instance.transferred_at = timezone.now()
            else:
                instance.transferred_to = None
                instance.transferred_at = None
        
        return super().update(instance, validated_data)


class AdminAbbatoirListSerializer(serializers.ModelSerializer):
    """Serializer for listing abbatoirs for selection dropdowns"""
    full_name = serializers.SerializerMethodField()
    location = serializers.CharField(source='profile.address', read_only=True)
    phone = serializers.CharField(source='profile.phone', read_only=True)
    animal_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 
                  'full_name', 'location', 'phone', 'animal_count']

    def get_full_name(self, obj):
        full_name = f"{obj.first_name} {obj.last_name}".strip()
        return full_name if full_name else obj.username

    def get_animal_count(self, obj):
        return obj.animals.count()

