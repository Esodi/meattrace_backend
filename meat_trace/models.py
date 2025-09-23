from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
import qrcode
import os
import uuid
from django.conf import settings

# Create your models here.

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('Farmer', 'Farmer'),
        ('ProcessingUnit', 'Processing Unit'),
        ('Shop', 'Shop'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Farmer')

    def __str__(self):
        return f"{self.user.username} - {self.role}"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()

class Animal(models.Model):
    SPECIES_CHOICES = [
        ('cow', 'Cow'),
        ('pig', 'Pig'),
        ('chicken', 'Chicken'),
        ('sheep', 'Sheep'),
        ('goat', 'Goat'),
    ]

    farmer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='animals')
    species = models.CharField(max_length=20, choices=SPECIES_CHOICES, default='cow')
    age = models.PositiveIntegerField(default=0, help_text="Age in months")
    weight = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0)], help_text="Weight in kg")
    created_at = models.DateTimeField(default=timezone.now)
    slaughtered = models.BooleanField(default=False)
    slaughtered_at = models.DateTimeField(null=True, blank=True)
    # Transfer fields
    transferred_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='transferred_animals')
    transferred_at = models.DateTimeField(null=True, blank=True)
    # Receive fields
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_animals')
    received_at = models.DateTimeField(null=True, blank=True)
    # Auto-generated unique identifier (primary key for internal use)
    animal_id = models.CharField(max_length=50, unique=True, editable=False, default='', help_text="Auto-generated unique animal identifier")
    # User-friendly optional name/tag
    animal_name = models.CharField(max_length=100, blank=True, null=True, help_text="Optional custom animal name or tag")
    breed = models.CharField(max_length=100, blank=True, null=True, help_text="Animal breed")
    farm_name = models.CharField(max_length=100, blank=True, null=True, help_text="Farm name")
    health_status = models.CharField(max_length=50, blank=True, null=True, help_text="Animal health status (e.g., Healthy, Sick, Under Treatment)")

    def save(self, *args, **kwargs):
        if not self.animal_id:
            self.animal_id = self._generate_animal_id()
        super().save(*args, **kwargs)

    def _generate_animal_id(self):
        """Generate a unique animal ID using UUID"""
        return f"ANIMAL_{uuid.uuid4().hex[:12].upper()}"

    def __str__(self):
        display_name = self.animal_name or self.animal_id
        return f"{display_name} ({self.species}) - {self.farmer.username}"

class ProductCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name

class ProcessingStage(models.Model):
    STAGE_CHOICES = [
        ('received', 'Received'),
        ('inspected', 'Inspected'),
        ('processed', 'Processed'),
        ('packaged', 'Packaged'),
        ('stored', 'Stored'),
        ('shipped', 'Shipped'),
    ]

    name = models.CharField(max_length=50, choices=STAGE_CHOICES, unique=True)
    description = models.TextField(blank=True, null=True)
    order = models.PositiveIntegerField(default=0, help_text="Order of processing stages")

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['order']

class ProductTimelineEvent(models.Model):
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='timeline_events')
    timestamp = models.DateTimeField(default=timezone.now)
    location = models.CharField(max_length=200)
    action = models.CharField(max_length=200)
    stage = models.ForeignKey(ProcessingStage, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.product.name} - {self.action} at {self.timestamp}"

    class Meta:
        ordering = ['timestamp']

class Product(models.Model):
    PRODUCT_TYPE_CHOICES = [
        ('meat', 'Meat'),
        ('milk', 'Milk'),
        ('eggs', 'Eggs'),
        ('wool', 'Wool'),
    ]

    WEIGHT_UNIT_CHOICES = [
        ('kg', 'Kilograms'),
        ('lbs', 'Pounds'),
        ('g', 'Grams'),
    ]

    processing_unit = models.ForeignKey(User, on_delete=models.CASCADE, related_name='products')
    animal = models.ForeignKey(Animal, on_delete=models.CASCADE, related_name='products')
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPE_CHOICES, default='meat')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    created_at = models.DateTimeField(default=timezone.now)

    # Additional fields for detailed product information
    name = models.CharField(max_length=200, default='Unnamed Product')
    batch_number = models.CharField(max_length=100, default='BATCH001')
    weight = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)], default=0)
    weight_unit = models.CharField(max_length=10, choices=WEIGHT_UNIT_CHOICES, default='kg')
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], default=0)
    description = models.TextField(blank=True, null=True)
    manufacturer = models.CharField(max_length=200, blank=True, null=True)
    category = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL, null=True, blank=True)

    # QR code field for traceability
    qr_code = models.CharField(max_length=500, blank=True, null=True)

    # Transfer fields (similar to Animal model)
    transferred_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='transferred_products')
    transferred_at = models.DateTimeField(null=True, blank=True)
    # Receive fields
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_products')
    received_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.product_type}) - Batch {self.batch_number}"

class Inventory(models.Model):
    shop = models.ForeignKey(User, on_delete=models.CASCADE, related_name='inventory')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='inventory')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    min_stock_level = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], default=0)
    last_updated = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ['shop', 'product']

    def __str__(self):
        return f"{self.shop.username} - {self.product.name} - {self.quantity}"

    @property
    def is_low_stock(self):
        return self.quantity <= self.min_stock_level

class Receipt(models.Model):
    shop = models.ForeignKey(User, on_delete=models.CASCADE, related_name='receipts')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='receipts')
    received_quantity = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    received_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Receipt {self.id} - {self.shop.username} - {self.product.product_type}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update inventory when receipt is created
        inventory, created = Inventory.objects.get_or_create(
            shop=self.shop,
            product=self.product,
            defaults={'quantity': 0}
        )
        inventory.quantity += self.received_quantity
        inventory.last_updated = timezone.now()
        inventory.save()

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('preparing', 'Preparing'),
        ('ready', 'Ready for Pickup'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    shop = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shop_orders')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    delivery_address = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Order {self.id} - {self.customer.username} - {self.status}"

    def update_total_amount(self):
        """Update total amount based on order items"""
        total = sum(item.subtotal for item in self.items.all())
        self.total_amount = total
        self.save()

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

    def save(self, *args, **kwargs):
        self.subtotal = self.quantity * self.unit_price
        super().save(*args, **kwargs)
        self.order.update_total_amount()

@receiver(post_save, sender=Product)
def generate_product_qr_code(sender, instance, created, **kwargs):
    """Generate QR code for new products"""
    if created and not instance.qr_code:
        try:
            # Generate the URL for the product API endpoint
            url = f"{getattr(settings, 'SITE_URL', 'http://localhost:8000')}/api/v2/products/{instance.id}/"

            # Create QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(url)
            qr.make(fit=True)

            # Create the image
            img = qr.make_image(fill_color="black", back_color="white")

            # Ensure the qr_codes directory exists
            qr_dir = os.path.join(settings.MEDIA_ROOT, 'qr_codes')
            os.makedirs(qr_dir, exist_ok=True)

            # Save the image
            filename = f"qr_{instance.id}.png"
            filepath = os.path.join(qr_dir, filename)
            img.save(filepath)

            # Update the instance with the relative path
            instance.qr_code = f"qr_codes/{filename}"
            instance.save(update_fields=['qr_code'])

        except Exception as e:
            # Log the error but don't fail the product creation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to generate QR code for product {instance.id}: {str(e)}")
