from rest_framework import serializers
from django.utils import timezone
from django.contrib.auth.models import User
from .models import Animal, Product, Receipt, UserProfile, ProductCategory, ProcessingStage, ProductTimelineEvent, Inventory, Order, OrderItem

class AnimalSerializer(serializers.ModelSerializer):
    farmer = serializers.PrimaryKeyRelatedField(read_only=True)
    farmer_username = serializers.StringRelatedField(source='farmer', read_only=True)

    class Meta:
        model = Animal
        fields = '__all__'
        read_only_fields = ['animal_id']  # Auto-generated, not editable by users

    def validate_slaughtered_at(self, value):
        if value and value < self.instance.created_at if self.instance else value < timezone.now():
            raise serializers.ValidationError("Slaughter date cannot be before creation date.")
        return value

class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = '__all__'

class ProcessingStageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessingStage
        fields = '__all__'

class ProductTimelineEventSerializer(serializers.ModelSerializer):
    stage = ProcessingStageSerializer(read_only=True)
    stage_id = serializers.PrimaryKeyRelatedField(
        queryset=ProcessingStage.objects.all(), source='stage', write_only=True, required=False
    )

    class Meta:
        model = ProductTimelineEvent
        fields = '__all__'

class ProductSerializer(serializers.ModelSerializer):
    animal = AnimalSerializer(read_only=True)
    animal_id = serializers.PrimaryKeyRelatedField(
        queryset=Animal.objects.all(), source='animal', write_only=True
    )
    processing_unit = serializers.StringRelatedField(read_only=True)
    category = ProductCategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=ProductCategory.objects.all(), source='category', write_only=True, required=False
    )
    timeline = ProductTimelineEventSerializer(source='timeline_events', many=True, read_only=True)

    # Transfer related fields
    transferred_to_username = serializers.StringRelatedField(source='transferred_to', read_only=True)
    received_by_username = serializers.StringRelatedField(source='received_by', read_only=True)

    class Meta:
        model = Product
        fields = '__all__'

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be positive.")
        return value

    def validate_weight(self, value):
        if value <= 0:
            raise serializers.ValidationError("Weight must be positive.")
        return value

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative.")
        return value

class InventorySerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )
    shop = serializers.StringRelatedField(read_only=True)
    is_low_stock = serializers.ReadOnlyField()

    class Meta:
        model = Inventory
        fields = '__all__'

    def validate_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("Quantity cannot be negative.")
        return value

    def validate_min_stock_level(self, value):
        if value < 0:
            raise serializers.ValidationError("Minimum stock level cannot be negative.")
        return value

class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )

    class Meta:
        model = OrderItem
        fields = '__all__'

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be positive.")
        return value

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    customer = serializers.StringRelatedField(read_only=True)
    shop = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Order
        fields = '__all__'

    def validate_total_amount(self, value):
        if value < 0:
            raise serializers.ValidationError("Total amount cannot be negative.")
        return value

    def create(self, validated_data):
        # Set customer from request user if not provided
        if 'customer' not in validated_data:
            validated_data['customer'] = self.context['request'].user
        return super().create(validated_data)

class ReceiptSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )
    shop = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Receipt
        fields = '__all__'

    def validate_received_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Received quantity must be positive.")
        return value

    def validate_received_at(self, value):
        if value > timezone.now():
            raise serializers.ValidationError("Receipt date cannot be in the future.")
        return value


class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = UserProfile
        fields = ['username', 'email', 'role']