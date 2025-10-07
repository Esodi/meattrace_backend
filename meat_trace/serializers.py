from rest_framework import serializers
from django.utils import timezone
from django.contrib.auth.models import User
from .models import Animal, Product, Receipt, UserProfile, ProductCategory, ProcessingStage, ProductTimelineEvent, Inventory, Order, OrderItem, CarcassMeasurement

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
class CarcassMeasurementSerializer(serializers.ModelSerializer):
    animal = AnimalSerializer(read_only=True)
    animal_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = CarcassMeasurement
        fields = '__all__'

    def create(self, validated_data):
        animal_id = validated_data.pop('animal_id')
        animal = Animal.objects.get(id=animal_id)
        validated_data['animal'] = animal
        return super().create(validated_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['animal_id'] = instance.animal.id
        return data

    def validate_animal_id(self, value):
        """Validate that carcass measurement doesn't already exist for this animal"""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Validating animal_id: {value}")

        # Get the animal instance
        try:
            animal = Animal.objects.get(id=value)
        except Animal.DoesNotExist:
            raise serializers.ValidationError("Animal not found.")

        if CarcassMeasurement.objects.filter(animal=animal).exists():
            logger.warning(f"Carcass measurement already exists for animal {value}")
            raise serializers.ValidationError("Carcass measurement already exists for this animal.")
        logger.info(f"Animal validation passed for animal {value}")
        return value

    def validate_measurements(self, value):
        """Validate the measurements JSON structure"""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Validating measurements: {value}")

        if not isinstance(value, dict):
            logger.warning("Measurements is not a dictionary")
            raise serializers.ValidationError("Measurements must be a dictionary.")

        for key, measurement in value.items():
            logger.info(f"Validating measurement '{key}': {measurement}")
            if not isinstance(measurement, dict):
                logger.warning(f"Measurement '{key}' is not a dictionary")
                raise serializers.ValidationError(f"Measurement '{key}' must be a dictionary with 'value' and 'unit' keys.")

            if 'value' not in measurement:
                logger.warning(f"Measurement '{key}' missing 'value' field")
                raise serializers.ValidationError(f"Measurement '{key}' must have a 'value' field.")

            if 'unit' not in measurement:
                logger.warning(f"Measurement '{key}' missing 'unit' field")
                raise serializers.ValidationError(f"Measurement '{key}' must have a 'unit' field.")

            # Validate value is a number
            try:
                float(measurement['value'])
            except (ValueError, TypeError):
                logger.warning(f"Measurement '{key}' value is not a number: {measurement['value']}")
                raise serializers.ValidationError(f"Measurement '{key}' value must be a number.")

            # Validate unit is valid
            if measurement['unit'] not in ['kg', 'lbs', 'g']:
                logger.warning(f"Measurement '{key}' invalid unit: {measurement['unit']}")
                raise serializers.ValidationError(f"Measurement '{key}' unit must be one of: kg, lbs, g.")

        logger.info("Measurements validation passed")
        return value

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
        fields = ['id', 'order', 'product', 'quantity', 'unit_price', 'subtotal', 'product_id']
        extra_kwargs = {
            'order': {'required': False}  # Not required when creating via order
        }

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be positive.")
        return value

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    items_data = OrderItemSerializer(many=True, write_only=True, required=False)
    customer = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False)
    shop = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False)

    class Meta:
        model = Order
        fields = ['id', 'customer', 'shop', 'status', 'total_amount', 'created_at', 'updated_at', 'delivery_address', 'notes', 'items', 'items_data']

    def validate_total_amount(self, value):
        if value < 0:
            raise serializers.ValidationError("Total amount cannot be negative.")
        return value

    def create(self, validated_data):
        # Extract items data before creating order
        items_data = validated_data.pop('items_data', [])

        # Only set customer and shop from request user if authenticated and not provided
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            if 'customer' not in validated_data:
                validated_data['customer'] = request.user
            if 'shop' not in validated_data:
                validated_data['shop'] = request.user

        # Create the order
        order = super().create(validated_data)

        # Create order items
        for item_data in items_data:
            OrderItem.objects.create(order=order, **item_data)

        # Update inventory if order is confirmed
        if order.status == 'confirmed':
            self._update_inventory_on_confirmation(order)

        return order

    def _update_inventory_on_confirmation(self, order):
        """Update inventory when order is confirmed"""
        from django.utils import timezone
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"Order {order.id} confirmed, updating inventory in serializer")

        for order_item in order.items.all():
            try:
                # Get or create inventory for this shop and product
                inventory, created = Inventory.objects.get_or_create(
                    shop=order.shop,
                    product=order_item.product,
                    defaults={'quantity': 0}
                )

                # Subtract ordered quantity from inventory
                old_quantity = inventory.quantity
                inventory.quantity = max(0, inventory.quantity - order_item.quantity)
                inventory.last_updated = timezone.now()
                inventory.save()

                logger.info(f"Updated inventory for product {order_item.product.name}: {old_quantity} -> {inventory.quantity}")

            except Exception as e:
                logger.error(f"Failed to update inventory for order item {order_item.id}: {str(e)}")
                # Continue with other items even if one fails

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