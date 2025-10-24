from rest_framework import serializers
from django.utils import timezone
from django.contrib.auth.models import User
from .models import (
    Animal, Product, Receipt, UserProfile, ProductCategory, ProcessingStage,
    ProductTimelineEvent, Inventory, Order, OrderItem, CarcassMeasurement,
    SlaughterPart, ProcessingUnit, ProcessingUnitUser, ProductIngredient,
    Shop, ShopUser, UserAuditLog, JoinRequest, Notification, Activity,
    SystemAlert, PerformanceMetric, ComplianceAudit, Certification,
    SystemHealth, SecurityLog, TransferRequest, BackupSchedule, Sale, SaleItem
)


class UserAuditLogSerializer(serializers.ModelSerializer):
    performed_by_username = serializers.CharField(source='performed_by.username', read_only=True)
    affected_user_username = serializers.CharField(source='affected_user.username', read_only=True)
    processing_unit_name = serializers.CharField(source='processing_unit.name', read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)

    class Meta:
        model = UserAuditLog
        fields = [
            'id', 'performed_by', 'performed_by_username', 'affected_user',
            'affected_user_username', 'processing_unit', 'processing_unit_name',
            'shop', 'shop_name', 'action', 'description', 'old_values',
            'new_values', 'metadata', 'timestamp'
        ]
        read_only_fields = ['id', 'timestamp']


class ProcessingUnitUserSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    invited_by_username = serializers.CharField(source='invited_by.username', read_only=True)
    processing_unit_name = serializers.CharField(source='processing_unit.name', read_only=True)

    class Meta:
        model = ProcessingUnitUser
        fields = [
            'id', 'user', 'user_username', 'user_email', 'processing_unit',
            'processing_unit_name', 'role', 'permissions', 'granular_permissions',
            'invited_by', 'invited_by_username', 'invited_at', 'joined_at',
            'is_active', 'is_suspended', 'suspension_reason', 'suspension_date',
            'last_active'
        ]
        read_only_fields = ['id', 'invited_at', 'joined_at', 'invited_by_username', 'processing_unit_name']


class AnimalSerializer(serializers.ModelSerializer):
    farmer_username = serializers.CharField(source='farmer.username', read_only=True)
    transferred_to_name = serializers.CharField(source='transferred_to.name', read_only=True, allow_null=True)
    received_by_username = serializers.CharField(source='received_by.username', read_only=True, allow_null=True)
    is_split_carcass = serializers.BooleanField(read_only=True)
    has_slaughter_parts = serializers.BooleanField(read_only=True)
    slaughter_parts = serializers.SerializerMethodField()
    carcass_measurement = serializers.SerializerMethodField()
    
    # Lifecycle status fields
    lifecycle_status = serializers.CharField(read_only=True)
    is_healthy = serializers.BooleanField(read_only=True)
    is_slaughtered_status = serializers.BooleanField(read_only=True)
    is_transferred_status = serializers.BooleanField(read_only=True)
    is_semi_transferred_status = serializers.BooleanField(read_only=True)

    class Meta:
        model = Animal
        fields = [
            'id', 'farmer', 'farmer_username', 'species', 'age', 'live_weight',
            'created_at', 'slaughtered', 'slaughtered_at', 'transferred_to',
            'transferred_to_name', 'transferred_at', 'received_by',
            'received_by_username', 'received_at', 'processed', 'animal_id',
            'animal_name', 'breed', 'health_status', 'abbatoir_name', 'photo',
            'gender', 'notes',
            'is_split_carcass', 'has_slaughter_parts', 'slaughter_parts', 'carcass_measurement',
            'age_in_years', 'age_in_days',
            'lifecycle_status', 'is_healthy', 'is_slaughtered_status',
            'is_transferred_status', 'is_semi_transferred_status'
        ]
        read_only_fields = ['id', 'created_at', 'farmer_username', 'transferred_to_name', 'received_by_username',
                           'is_split_carcass', 'has_slaughter_parts', 'age_in_years', 'age_in_days', 'farmer',
                           'lifecycle_status', 'is_healthy', 'is_slaughtered_status',
                           'is_transferred_status', 'is_semi_transferred_status']

    def validate_health_status(self, value):
        # Optional: enforce health status normalization (allow any but trim)
        if value is None:
            return value
        return value.strip()

    def validate_age(self, value):
        """Validate age is reasonable (not negative, not too old for livestock)"""
        if value is not None:
            if value < 0:
                raise serializers.ValidationError("Age cannot be negative")
            if value > 1200:  # 100 years in months
                raise serializers.ValidationError("Age seems unreasonably high (more than 100 years)")
        return value

    def validate_live_weight(self, value):
        """Validate live weight is reasonable"""
        if value is not None:
            if value < 0:
                raise serializers.ValidationError("Live weight cannot be negative")
            if value > 5000:  # 5 tons - very heavy for livestock
                raise serializers.ValidationError("Live weight seems unreasonably high")
        return value
    
    def get_slaughter_parts(self, obj):
        """Include slaughter parts if they exist"""
        if obj.has_slaughter_parts:
            from .serializers import SlaughterPartSerializer
            parts = obj.slaughter_parts.all()
            return SlaughterPartSerializer(parts, many=True).data
        return []
    
    def get_carcass_measurement(self, obj):
        """Include carcass measurement if it exists"""
        try:
            measurement = obj.carcass_measurement
        except CarcassMeasurement.DoesNotExist:
            return None
        from .serializers import CarcassMeasurementSerializer
        return CarcassMeasurementSerializer(measurement).data


class ProductSerializer(serializers.ModelSerializer):
    # ProcessingUnit model exposes `name` (not `username`). Fix source to use the correct attribute.
    processing_unit_name = serializers.CharField(source='processing_unit.name', read_only=True)
    animal_animal_id = serializers.CharField(source='animal.animal_id', read_only=True)
    animal_species = serializers.CharField(source='animal.species', read_only=True)
    transferred_to_name = serializers.CharField(source='transferred_to.name', read_only=True, allow_null=True)
    received_by_shop_name = serializers.CharField(source='received_by_shop.name', read_only=True, allow_null=True)
    slaughter_part_name = serializers.SerializerMethodField()
    slaughter_part_type = serializers.CharField(source='slaughter_part.part_type', read_only=True, allow_null=True)

    def get_slaughter_part_name(self, obj):
        """Get the display name of the slaughter part"""
        if obj.slaughter_part:
            # Return the display name from the PART_CHOICES
            return obj.slaughter_part.get_part_type_display()
        return None

    class Meta:
        model = Product
        fields = [
            'id', 'processing_unit', 'processing_unit_name', 'animal', 'animal_animal_id',
            'animal_species', 'slaughter_part', 'slaughter_part_name', 'slaughter_part_type',
            'name', 'product_type', 'quantity', 'weight', 'weight_unit',
            'price', 'description', 'manufacturer', 'batch_number', 'category', 'created_at',
            'transferred_to', 'transferred_to_name', 'transferred_at', 'received_by_shop',
            'received_by_shop_name', 'received_at', 'qr_code'
        ]
        read_only_fields = [
            'id', 'created_at', 'processing_unit_name', 'animal_animal_id', 'animal_species',
            'slaughter_part_name', 'slaughter_part_type', 'transferred_to_name', 'received_by_shop_name'
        ]


class ReceiptSerializer(serializers.ModelSerializer):
    shop_name = serializers.CharField(source='shop.name', read_only=True)

    class Meta:
        model = Receipt
        fields = ['id', 'product', 'shop', 'shop_name', 'received_quantity', 'received_at']
        read_only_fields = ['id', 'received_at', 'shop_name']


class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = ['id', 'name', 'description']


class ProcessingStageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessingStage
        fields = ['id', 'name', 'description', 'order']


class ProductTimelineEventSerializer(serializers.ModelSerializer):
    stage_name = serializers.CharField(source='stage.name', read_only=True)

    class Meta:
        model = ProductTimelineEvent
        fields = ['id', 'product', 'stage', 'stage_name', 'location', 'action', 'timestamp']
        read_only_fields = ['id', 'timestamp']


class InventorySerializer(serializers.ModelSerializer):
    shop_username = serializers.CharField(source='shop.username', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = Inventory
        fields = ['id', 'product', 'product_name', 'shop', 'shop_username', 'quantity', 'min_stock_level', 'last_updated']
        read_only_fields = ['id', 'last_updated', 'shop_username', 'product_name']


class OrderSerializer(serializers.ModelSerializer):
    customer_username = serializers.CharField(source='customer.username', read_only=True)
    shop_username = serializers.CharField(source='shop.username', read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'customer', 'customer_username', 'shop', 'shop_username', 'status',
            'total_amount', 'created_at', 'updated_at', 'delivery_address', 'notes', 'qr_code'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'customer_username', 'shop_username']


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    order_customer_username = serializers.CharField(source='order.customer.username', read_only=True)
    order_shop_username = serializers.CharField(source='order.shop.username', read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            'id', 'order', 'product', 'product_name', 'quantity', 'unit_price',
            'subtotal', 'order_customer_username', 'order_shop_username'
        ]
        read_only_fields = ['id', 'subtotal', 'order_customer_username', 'order_shop_username']


class CarcassMeasurementSerializer(serializers.ModelSerializer):
    animal_animal_id = serializers.CharField(source='animal.animal_id', read_only=True)
    animal_species = serializers.CharField(source='animal.species', read_only=True)
    animal_farmer_username = serializers.CharField(source='animal.farmer.username', read_only=True)

    class Meta:
        model = CarcassMeasurement
        fields = [
            'id', 'animal', 'animal_animal_id', 'animal_species', 'animal_farmer_username',
            'carcass_type', 'measurements', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'animal_animal_id', 'animal_species', 'animal_farmer_username']


class SlaughterPartSerializer(serializers.ModelSerializer):
    animal_animal_id = serializers.CharField(source='animal.animal_id', read_only=True)
    animal_species = serializers.CharField(source='animal.species', read_only=True)
    transferred_to_name = serializers.CharField(source='transferred_to.name', read_only=True, allow_null=True)
    received_by_username = serializers.CharField(source='received_by.username', read_only=True, allow_null=True)

    class Meta:
        model = SlaughterPart
        fields = [
            'id', 'animal', 'animal_animal_id', 'animal_species', 'part_type', 'weight',
            'weight_unit', 'description', 'created_at', 'transferred_to', 'transferred_to_name',
            'transferred_at', 'received_by', 'received_by_username', 'received_at',
            'used_in_product', 'is_selected_for_transfer'
        ]
        read_only_fields = ['id', 'created_at', 'animal_animal_id', 'animal_species', 'transferred_to_name', 'received_by_username']


class ProcessingUnitSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        print(f"[PROCESSING_UNIT_SERIALIZER] Serializing unit ID {instance.id}: {instance.name}")
        return data

    class Meta:
        model = ProcessingUnit
        fields = [
            'id', 'name', 'description', 'location', 'contact_email', 'contact_phone',
            'license_number', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductIngredientSerializer(serializers.ModelSerializer):
    slaughter_part_part_type = serializers.CharField(source='slaughter_part.part_type', read_only=True)
    slaughter_part_weight = serializers.DecimalField(source='slaughter_part.weight', max_digits=5, decimal_places=2, read_only=True)

    class Meta:
        model = ProductIngredient
        fields = [
            'id', 'product', 'slaughter_part', 'slaughter_part_part_type',
            'slaughter_part_weight', 'quantity_used', 'quantity_unit'
        ]
        read_only_fields = ['id', 'slaughter_part_part_type', 'slaughter_part_weight']


class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = [
            'id', 'name', 'description', 'location', 'contact_email', 'contact_phone',
            'business_license', 'tax_id', 'created_at', 'updated_at', 'is_active'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ShopUserSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    invited_by_username = serializers.CharField(source='invited_by.username', read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)

    class Meta:
        model = ShopUser
        fields = [
            'id', 'user', 'user_username', 'user_email', 'shop', 'shop_name',
            'role', 'permissions', 'invited_by', 'invited_by_username',
            'invited_at', 'joined_at', 'is_active'
        ]
        read_only_fields = ['id', 'invited_at', 'joined_at', 'invited_by_username', 'shop_name']


class JoinRequestSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    processing_unit_name = serializers.CharField(source='processing_unit.name', read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    reviewed_by_username = serializers.CharField(source='reviewed_by.username', read_only=True)

    class Meta:
        model = JoinRequest
        fields = [
            'id', 'user', 'user_username', 'user_email', 'request_type', 'status',
            'processing_unit', 'processing_unit_name', 'shop', 'shop_name',
            'requested_role', 'message', 'qualifications', 'reviewed_by',
            'reviewed_by_username', 'response_message', 'reviewed_at',
            'expires_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'reviewed_by_username']


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'title', 'message', 'data', 'is_read',
            'read_at', 'action_url', 'action_text', 'created_at', 'expires_at'
        ]
        read_only_fields = ['id', 'created_at']


class ActivitySerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Activity
        fields = [
            'id', 'user', 'username', 'activity_type', 'title', 'description',
            'entity_id', 'entity_type', 'metadata', 'target_route', 'timestamp',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'username']

    def create(self, validated_data):
        # Set user from request context if not provided
        if 'user' not in validated_data:
            validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class UserProfileSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_first_name = serializers.CharField(source='user.first_name', read_only=True)
    user_last_name = serializers.CharField(source='user.last_name', read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            'id', 'user', 'user_username', 'user_email', 'user_first_name', 'user_last_name',
            'role', 'processing_unit', 'shop', 'is_profile_complete', 'profile_completion_step',
            'avatar', 'phone', 'address', 'bio', 'preferred_species', 'notification_preferences',
            'is_email_verified', 'is_phone_verified', 'verification_token', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'user_username', 'user_email',
                           'user_first_name', 'user_last_name', 'verification_token']

    def validate_role(self, value):
        """Ensure role is one of the valid choices"""
        valid_roles = ['farmer', 'processing_unit', 'shop']
        if value not in valid_roles:
            raise serializers.ValidationError(f"Role must be one of: {', '.join(valid_roles)}")
        return value

    def validate_phone(self, value):
        """Validate phone number format"""
        if value:
            import re
            # Basic phone validation - allow digits, spaces, hyphens, plus signs
            if not re.match(r'^[\d\s\-\+\(\)]+$', value):
                raise serializers.ValidationError("Phone number contains invalid characters")
        return value


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN DASHBOARD SERIALIZERS
# ══════════════════════════════════════════════════════════════════════════════

class SystemAlertSerializer(serializers.ModelSerializer):
    acknowledged_by_username = serializers.CharField(source='acknowledged_by.username', read_only=True)
    processing_unit_name = serializers.CharField(source='processing_unit.name', read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = SystemAlert
        fields = [
            'id', 'title', 'message', 'alert_type', 'category', 'processing_unit',
            'processing_unit_name', 'shop', 'shop_name', 'user', 'user_username',
            'is_active', 'is_acknowledged', 'acknowledged_by', 'acknowledged_by_username',
            'acknowledged_at', 'auto_resolve', 'resolved_at', 'metadata',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'acknowledged_by_username']


class PerformanceMetricSerializer(serializers.ModelSerializer):
    processing_unit_name = serializers.CharField(source='processing_unit.name', read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)

    class Meta:
        model = PerformanceMetric
        fields = [
            'id', 'name', 'metric_type', 'value', 'unit', 'processing_unit',
            'processing_unit_name', 'shop', 'shop_name', 'period_start', 'period_end',
            'target_value', 'warning_threshold', 'critical_threshold', 'metadata', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ComplianceAuditSerializer(serializers.ModelSerializer):
    processing_unit_name = serializers.CharField(source='processing_unit.name', read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)

    class Meta:
        model = ComplianceAudit
        fields = [
            'id', 'title', 'audit_type', 'status', 'processing_unit', 'processing_unit_name',
            'shop', 'shop_name', 'auditor', 'auditor_organization', 'scheduled_date',
            'completed_date', 'score', 'findings', 'recommendations', 'follow_up_required',
            'follow_up_date', 'follow_up_notes', 'metadata', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CertificationSerializer(serializers.ModelSerializer):
    processing_unit_name = serializers.CharField(source='processing_unit.name', read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)

    class Meta:
        model = Certification
        fields = [
            'id', 'name', 'cert_type', 'status', 'processing_unit', 'processing_unit_name',
            'shop', 'shop_name', 'issuing_authority', 'certificate_number', 'issue_date',
            'expiry_date', 'certificate_file', 'notes', 'metadata', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class SystemHealthSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemHealth
        fields = [
            'id', 'component', 'status', 'response_time', 'uptime_percentage',
            'message', 'last_check', 'next_check', 'warning_threshold',
            'critical_threshold', 'metadata'
        ]
        read_only_fields = ['id']


class SecurityLogSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    processing_unit_name = serializers.CharField(source='processing_unit.name', read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)

    class Meta:
        model = SecurityLog
        fields = [
            'id', 'user', 'user_username', 'event_type', 'severity', 'description',
            'ip_address', 'user_agent', 'processing_unit', 'processing_unit_name',
            'shop', 'shop_name', 'resource', 'action', 'metadata', 'timestamp'
        ]
        read_only_fields = ['id', 'timestamp']


class TransferRequestSerializer(serializers.ModelSerializer):
    from_processing_unit_name = serializers.CharField(source='from_processing_unit.name', read_only=True)
    to_processing_unit_name = serializers.CharField(source='to_processing_unit.name', read_only=True)
    requested_by_username = serializers.CharField(source='requested_by.username', read_only=True)
    approved_by_username = serializers.CharField(source='approved_by.username', read_only=True)
    animal_animal_id = serializers.CharField(source='animal.animal_id', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = TransferRequest
        fields = [
            'id', 'request_type', 'status', 'from_processing_unit', 'from_processing_unit_name',
            'to_processing_unit', 'to_processing_unit_name', 'requested_by', 'requested_by_username',
            'approved_by', 'approved_by_username', 'approved_at', 'animal', 'animal_animal_id',
            'product', 'product_name', 'quantity', 'notes', 'approval_required', 'priority',
            'metadata', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class BackupScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = BackupSchedule
        fields = [
            'id', 'name', 'frequency', 'backup_type', 'scheduled_time', 'last_run',
            'next_run', 'include_database', 'include_files', 'include_media',
            'retention_days', 'is_active', 'last_status', 'metadata', 'created_at', 'updated_at'
        ]


class SaleItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    
    class Meta:
        model = SaleItem
        fields = ['id', 'sale', 'product', 'product_name', 'quantity', 'unit_price', 'subtotal']
        read_only_fields = ['id', 'subtotal', 'sale']


class SaleSerializer(serializers.ModelSerializer):
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    sold_by_username = serializers.CharField(source='sold_by.username', read_only=True)
    items = SaleItemSerializer(many=True)
    
    class Meta:
        model = Sale
        fields = [
            'id', 'shop', 'shop_name', 'sold_by', 'sold_by_username',
            'customer_name', 'customer_phone', 'total_amount', 'payment_method',
            'created_at', 'qr_code', 'items'
        ]
        read_only_fields = ['id', 'created_at', 'qr_code', 'shop_name', 'sold_by_username']
    
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        sale = Sale.objects.create(**validated_data)
        
        for item_data in items_data:
            SaleItem.objects.create(sale=sale, **item_data)
        
        return sale
        read_only_fields = ['id', 'created_at', 'updated_at']
