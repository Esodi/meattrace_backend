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
import json
from decimal import Decimal

# Create your models here.

class ProcessingUnit(models.Model):
    """Represents a processing unit that can have multiple users with different roles"""
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, null=True)
    location = models.CharField(max_length=200, blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    license_number = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class ProcessingUnitUser(models.Model):
    """Links users to processing units with specific roles and permissions"""
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('manager', 'Manager'),
        ('supervisor', 'Supervisor'),
        ('worker', 'Worker'),
        ('quality_control', 'Quality Control'),
    ]

    PERMISSION_CHOICES = [
        ('read', 'Read Only'),
        ('write', 'Read/Write'),
        ('admin', 'Full Admin'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='processing_unit_memberships')
    processing_unit = models.ForeignKey(ProcessingUnit, on_delete=models.CASCADE, related_name='members')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='worker')
    permissions = models.CharField(max_length=20, choices=PERMISSION_CHOICES, default='write')
    # Granular permissions as JSONField for detailed access control
    granular_permissions = models.JSONField(default=dict, blank=True, help_text="JSON object defining specific permissions")
    invited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_invitations')
    invited_at = models.DateTimeField(default=timezone.now)
    joined_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    # Suspension fields
    is_suspended = models.BooleanField(default=False, help_text="Whether the user is currently suspended")
    suspension_reason = models.TextField(blank=True, null=True, help_text="Reason for suspension")
    suspension_date = models.DateTimeField(null=True, blank=True, help_text="Date when user was suspended")
    # Activity tracking
    last_active = models.DateTimeField(null=True, blank=True, help_text="Last time user was active in the system")

    class Meta:
        unique_together = ['user', 'processing_unit']

    def __str__(self):
        return f"{self.user.username} - {self.processing_unit.name} ({self.role})"


class Shop(models.Model):
    """Represents a registered shop with business information"""
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, null=True)
    location = models.CharField(max_length=200, blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    business_license = models.CharField(max_length=100, blank=True, null=True)
    tax_id = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class ShopUser(models.Model):
    """Links users to shops with specific roles and permissions"""
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('manager', 'Manager'),
        ('salesperson', 'Salesperson'),
        ('cashier', 'Cashier'),
        ('inventory_clerk', 'Inventory Clerk'),
    ]

    PERMISSION_CHOICES = [
        ('read', 'Read Only'),
        ('write', 'Read/Write'),
        ('admin', 'Full Admin'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shop_memberships')
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='members')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='salesperson')
    permissions = models.CharField(max_length=20, choices=PERMISSION_CHOICES, default='write')
    invited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_shop_invitations')
    invited_at = models.DateTimeField(default=timezone.now)
    joined_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['user', 'shop']

    def __str__(self):
        return f"{self.user.username} - {self.shop.name} ({self.role})"


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('farmer', 'Farmer'),
        ('processing_unit', 'Processing Unit'),
        ('shop', 'Shop'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='farmer')
    # Link to processing unit for users who are part of processing units
    processing_unit = models.ForeignKey(ProcessingUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name='user_profiles')
    # Link to shop for users who are part of shops
    shop = models.ForeignKey(Shop, on_delete=models.SET_NULL, null=True, blank=True, related_name='user_profiles')

    # Enhanced profile fields from design
    is_profile_complete = models.BooleanField(default=False)
    profile_completion_step = models.IntegerField(default=1)

    # Additional profile fields
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    bio = models.TextField(blank=True)

    # Preferences
    preferred_species = models.JSONField(default=list, blank=True)  # For farmers
    notification_preferences = models.JSONField(default=dict, blank=True)

    # Verification status
    is_email_verified = models.BooleanField(default=False)
    is_phone_verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.role}"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()


class UserAuditLog(models.Model):
    """Tracks all user management actions, permission changes, and security events"""
    ACTION_CHOICES = [
        ('user_invited', 'User Invited'),
        ('user_joined', 'User Joined'),
        ('user_suspended', 'User Suspended'),
        ('user_unsuspended', 'User Unsuspended'),
        ('user_removed', 'User Removed'),
        ('role_changed', 'Role Changed'),
        ('permissions_changed', 'Permissions Changed'),
        ('granular_permissions_changed', 'Granular Permissions Changed'),
        ('user_login', 'User Login'),
        ('user_logout', 'User Logout'),
        ('password_changed', 'Password Changed'),
        ('profile_updated', 'Profile Updated'),
        ('security_event', 'Security Event'),
    ]

    # The user who performed the action (admin/manager)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_actions')
    # The user who was affected by the action
    affected_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='audit_events')
    # The processing unit context (if applicable)
    processing_unit = models.ForeignKey(ProcessingUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    # The shop context (if applicable)
    shop = models.ForeignKey(Shop, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')

    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    description = models.TextField(help_text="Detailed description of the action performed")
    # Store old and new values for change tracking
    old_values = models.JSONField(default=dict, blank=True, help_text="Previous values before the change")
    new_values = models.JSONField(default=dict, blank=True, help_text="New values after the change")
    # Additional metadata
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional context or metadata")
    # IP address and user agent for security tracking
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)

    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['performed_by', 'timestamp']),
            models.Index(fields=['affected_user', 'timestamp']),
            models.Index(fields=['processing_unit', 'timestamp']),
            models.Index(fields=['shop', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
        ]

    def __str__(self):
        context = self.processing_unit.name if self.processing_unit else (self.shop.name if self.shop else 'System')
        return f"{self.action} by {self.performed_by.username if self.performed_by else 'System'} on {self.affected_user.username} in {context} at {self.timestamp}"

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
    age = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0)], help_text="Age in months")

    @property
    def age_in_years(self):
        """Calculate age in years from months"""
        return self.age / 12 if self.age else 0

    @property
    def age_in_days(self):
        """Calculate age in days from months (approximate)"""
        return self.age * Decimal('30.44') if self.age else 0  # Average days per month

    @property
    def weight_kg(self):
        """Alias for live_weight to maintain compatibility"""
        return self.live_weight

    live_weight = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0)], null=True, blank=True, help_text="Live weight in kg before slaughter")
    # Gender and notes - added to align with frontend register screen
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('unknown', 'Unknown'),
    ]
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='unknown', help_text="Animal gender")
    notes = models.TextField(blank=True, null=True, help_text="Additional notes about the animal")
    created_at = models.DateTimeField(default=timezone.now)
    slaughtered = models.BooleanField(default=False)
    slaughtered_at = models.DateTimeField(null=True, blank=True)
    # Transfer fields
    transferred_to = models.ForeignKey(ProcessingUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name='transferred_animals')
    transferred_at = models.DateTimeField(null=True, blank=True)
    # Receive fields
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_animals')
    received_at = models.DateTimeField(null=True, blank=True)
    # Auto-generated unique identifier (primary key for internal use)
    animal_id = models.CharField(max_length=50, unique=True, editable=False, default='', help_text="Auto-generated unique animal identifier")
    # User-friendly optional name/tag
    animal_name = models.CharField(max_length=100, blank=True, null=True, help_text="Optional custom animal name or tag")
    breed = models.CharField(max_length=100, blank=True, null=True, help_text="Animal breed")
    abbatoir_name = models.CharField(max_length=100, blank=True, null=True, help_text="Abbatoir name")
    health_status = models.CharField(max_length=50, blank=True, null=True, help_text="Animal health status (e.g., Healthy, Sick, Under Treatment)")
    processed = models.BooleanField(default=False, help_text="Indicates if the animal has been processed into products")
    photo = models.ImageField(upload_to='animal_photos/', blank=True, null=True, help_text="Animal photo")

    def save(self, *args, **kwargs):
        # Ensure photo field is properly handled
        if self.photo and hasattr(self.photo, 'name'):
            # Validate file extension
            allowed_extensions = ['jpg', 'jpeg', 'png', 'gif']
            file_extension = self.photo.name.split('.')[-1].lower()
            if file_extension not in allowed_extensions:
                raise ValueError(f"Unsupported file extension: {file_extension}. Allowed: {', '.join(allowed_extensions)}")

            # Validate file size (max 5MB)
            if self.photo.size > 5 * 1024 * 1024:
                raise ValueError("File size too large. Maximum allowed size is 5MB.")

        # Ensure animal_id exists
        if not self.animal_id:
            self.animal_id = self._generate_animal_id()

        super().save(*args, **kwargs)

    def _generate_animal_id(self):
        """Generate a unique animal ID using UUID"""
        return f"ANIMAL_{uuid.uuid4().hex[:12].upper()}"
    
    @property
    def is_split_carcass(self):
        """Check if this animal is a split carcass based on carcass measurement"""
        try:
            return hasattr(self, 'carcass_measurement') and self.carcass_measurement.carcass_type == 'split'
        except:
            return False
    
    @property
    def has_slaughter_parts(self):
        """Check if this animal has individual slaughter parts defined"""
        return self.slaughter_parts.exists()
    
    @property
    def lifecycle_status(self):
        """
        Determine the animal's lifecycle status based on four distinct categories:
        1. HEALTHY - Alive, in good condition, no transfers or processing
        2. SLAUGHTERED - Processed and no longer alive (but NOT transferred)
        3. TRANSFERRED - Entire body/all parts completely transferred
        4. SEMI-TRANSFERRED - Partially transferred (some parts moved, others remain)
        
        Priority order:
        1. Check transfer status first (whole animal or all parts)
        2. Check for partial transfers
        3. Check if slaughtered (but not transferred)
        4. Default to healthy
        """
        # Priority 1: Check if whole animal is transferred
        if self.transferred_to is not None:
            return 'TRANSFERRED'
        
        # Priority 2: Check for partial or complete part transfers
        if self.has_slaughter_parts:
            parts = self.slaughter_parts.all()
            transferred_parts = [p for p in parts if p.transferred_to is not None]
            
            if transferred_parts:
                # All parts transferred
                if len(transferred_parts) == len(parts):
                    return 'TRANSFERRED'
                # Some parts transferred but not all
                else:
                    return 'SEMI-TRANSFERRED'
        
        # Priority 3: Check if slaughtered (but not transferred)
        if self.slaughtered:
            return 'SLAUGHTERED'
        
        # Default: Animal is healthy and on the farm
        return 'HEALTHY'
    
    @property
    def is_healthy(self):
        """Check if animal is in HEALTHY status"""
        return self.lifecycle_status == 'HEALTHY'
    
    @property
    def is_slaughtered_status(self):
        """Check if animal is in SLAUGHTERED status"""
        return self.lifecycle_status == 'SLAUGHTERED'
    
    @property
    def is_transferred_status(self):
        """Check if animal is in TRANSFERRED status"""
        return self.lifecycle_status == 'TRANSFERRED'
    
    @property
    def is_semi_transferred_status(self):
        """Check if animal is in SEMI-TRANSFERRED status"""
        return self.lifecycle_status == 'SEMI-TRANSFERRED'

    def __str__(self):
        display_name = self.animal_name or self.animal_id
        return f"{display_name} ({self.species}) - {self.farmer.username}"
class SlaughterPart(models.Model):
    PART_CHOICES = [
        ('whole_carcass', 'Whole Carcass'),
        ('left_side', 'Left Side'),
        ('right_side', 'Right Side'),
        ('head', 'Head'),
        ('feet', 'Feet'),
        ('internal_organs', 'Internal Organs'),
        ('other', 'Other'),
    ]

    animal = models.ForeignKey(Animal, on_delete=models.CASCADE, related_name='slaughter_parts')
    part_type = models.CharField(max_length=20, choices=PART_CHOICES, default='whole_carcass')
    weight = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)], help_text="Weight of this part in kg")
    weight_unit = models.CharField(max_length=10, choices=[('kg', 'Kilograms'), ('lbs', 'Pounds'), ('g', 'Grams')], default='kg')
    description = models.TextField(blank=True, null=True, help_text="Additional description of the part")
    created_at = models.DateTimeField(default=timezone.now)

    # Transfer fields - changed to ProcessingUnit instead of User for consistency with Animal model
    transferred_to = models.ForeignKey('ProcessingUnit', on_delete=models.SET_NULL, null=True, blank=True, related_name='transferred_parts')
    transferred_at = models.DateTimeField(null=True, blank=True)
    # Receive fields
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_parts')
    received_at = models.DateTimeField(null=True, blank=True)

    # Track if this part has been used in a product
    used_in_product = models.BooleanField(default=False, help_text="Indicates if this part has been used to create a product")
    
    # Track whether part is selected for transfer/receive (for split carcass workflow)
    is_selected_for_transfer = models.BooleanField(default=False, help_text="Whether this part is selected for the current transfer")

    def __str__(self):
        return f"{self.part_type} of {self.animal.animal_id} ({self.weight} {self.weight_unit})"

    class Meta:
        unique_together = ['animal', 'part_type']  # Prevent duplicate parts for same animal


class ProductIngredient(models.Model):
    """Tracks which slaughter parts are used to create each product"""
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='ingredients')
    slaughter_part = models.ForeignKey(SlaughterPart, on_delete=models.CASCADE, related_name='product_ingredients')
    quantity_used = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)], help_text="Quantity of this part used in the product")
    quantity_unit = models.CharField(max_length=10, choices=[('kg', 'Kilograms'), ('lbs', 'Pounds'), ('g', 'Grams')], default='kg')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ['product', 'slaughter_part']  # Prevent duplicate ingredients for same product

    def __str__(self):
        return f"{self.slaughter_part.part_type} in {self.product.name} ({self.quantity_used} {self.quantity_unit})"


class CarcassMeasurement(models.Model):
    CARCASS_TYPE_CHOICES = [
        ('whole', 'Whole Carcass'),
        ('split', 'Split Carcass'),
    ]

    UNIT_CHOICES = [
        ('kg', 'Kilograms'),
        ('lbs', 'Pounds'),
        ('g', 'Grams'),
    ]

    animal = models.OneToOneField(Animal, on_delete=models.CASCADE, related_name='carcass_measurement')
    carcass_type = models.CharField(max_length=20, choices=CARCASS_TYPE_CHOICES, default='whole', help_text="Type of carcass measurement")
    # Whole carcass fields
    head_weight = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)], null=True, blank=True, help_text="Weight of head")
    torso_weight = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)], null=True, blank=True, help_text="Weight of torso")
    # Split carcass fields (aligned with frontend naming)
    front_legs_weight = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)], null=True, blank=True, help_text="Weight of front legs")
    hind_legs_weight = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)], null=True, blank=True, help_text="Weight of hind legs")
    feet_weight = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)], null=True, blank=True, help_text="Weight of feet")
    organs_weight = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)], null=True, blank=True, help_text="Weight of organs")
    weight_unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='kg', help_text="Unit for weight measurements")
    measurements = models.JSONField(blank=True, help_text="JSON object containing measurement data: {'head_weight': {'value': 5.2, 'unit': 'kg'}, 'torso_weight': {'value': 45.8, 'unit': 'kg'}}")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Carcass measurements for {self.animal.animal_id}"

    @property
    def calculated_total_weight(self):
        """Calculate total weight based on carcass type"""
        if self.carcass_type == 'whole':
            if self.head_weight is not None and self.torso_weight is not None:
                return self.head_weight + self.torso_weight
        elif self.carcass_type == 'split':
            if (self.front_legs_weight is not None and self.hind_legs_weight is not None and
                self.feet_weight is not None and self.organs_weight is not None):
                return (self.front_legs_weight + self.hind_legs_weight +
                       self.feet_weight + self.organs_weight)
        return None

    def clean(self):
        """Validate carcass measurement data"""
        from django.core.exceptions import ValidationError

        # Validate all weights are positive
        weight_fields = ['head_weight', 'torso_weight', 'front_legs_weight',
                        'hind_legs_weight', 'feet_weight', 'organs_weight']
        for field_name in weight_fields:
            weight = getattr(self, field_name)
            if weight is not None and weight <= 0:
                raise ValidationError(f"{field_name.replace('_', ' ').title()} must be positive.")

        # Validate required fields based on carcass_type
        if self.carcass_type == 'whole':
            if self.head_weight is None or self.torso_weight is None:
                raise ValidationError("For whole carcass, both head_weight and torso_weight are required.")
        elif self.carcass_type == 'split':
            # Use the declared split field names
            required_fields = ['front_legs_weight', 'hind_legs_weight', 'feet_weight', 'organs_weight']
            for field_name in required_fields:
                if getattr(self, field_name) is None:
                    raise ValidationError(f"For split carcass, {field_name.replace('_', ' ')} is required.")

    def get_measurement(self, key):
        """Get a specific measurement by key"""
        return self.measurements.get(key)

    def set_measurement(self, key, value, unit='kg'):
        """Set a specific measurement"""
        if not self.measurements:
            self.measurements = {}
        self.measurements[key] = {'value': value, 'unit': unit}
        self.save()

    def get_all_measurements(self):
        """Get all measurements as a list of dicts"""
        return [{'name': k, 'value': v['value'], 'unit': v['unit']} for k, v in self.measurements.items()]


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

    processing_unit = models.ForeignKey(ProcessingUnit, on_delete=models.CASCADE, related_name='products')
    animal = models.ForeignKey(Animal, on_delete=models.CASCADE, related_name='products')
    slaughter_part = models.ForeignKey(SlaughterPart, on_delete=models.SET_NULL, null=True, blank=True, related_name='products', help_text="The specific slaughter part this product was made from")
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

    # Transfer fields (products are transferred to Shop-level entities)
    transferred_to = models.ForeignKey(Shop, on_delete=models.SET_NULL, null=True, blank=True, related_name='transferred_products')
    transferred_at = models.DateTimeField(null=True, blank=True)
    # Receive fields (shop receives products, not individual users)
    received_by_shop = models.ForeignKey(Shop, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_products_as_shop')
    received_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        part_info = f" from {self.slaughter_part.get_part_type_display()}" if self.slaughter_part else ""
        return f"{self.name} ({self.product_type}){part_info} - Batch {self.batch_number}"

class Inventory(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='inventory')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='inventory')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    min_stock_level = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], default=0)
    last_updated = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ['shop', 'product']

    def __str__(self):
        return f"{self.shop.name} - {self.product.name} - {self.quantity}"

    @property
    def is_low_stock(self):
        return self.quantity <= self.min_stock_level

class Receipt(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='receipts')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='receipts')
    received_quantity = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    received_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Receipt {self.id} - {self.shop.name} - {self.product.product_type}"

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
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='orders')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    delivery_address = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    # QR code field for processing orders
    qr_code = models.CharField(max_length=500, blank=True, null=True)

    def __str__(self):
        return f"Order {self.id} - {self.customer.username} - {self.shop.name} - {self.status}"

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
    """Generate QR code for new products that links to the product info page"""
    if created and not instance.qr_code:
        try:
            # Generate the URL for the product info HTML page
            url = f"{getattr(settings, 'SITE_URL', 'http://localhost:8000')}/api/v2/product-info/view/{instance.id}/"

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


@receiver(post_save, sender=Order)
def generate_order_qr_code(sender, instance, created, **kwargs):
    """Generate QR code for orders using Shop fields safely"""
    if created and not instance.qr_code:
        try:
            # If there's no shop attached, skip
            if not instance.shop:
                return

            # Build a shop-oriented QR payload (safe fields on Shop)
            qr_data = {
                'type': 'shop_order',
                'order_id': instance.id,
                'shop_id': instance.shop.id,
                'shop_name': instance.shop.name,
                'customer_id': instance.customer.id if instance.customer else None,
                'customer_name': instance.customer.username if instance.customer else None,
                'status': instance.status,
                'total_amount': float(instance.total_amount) if instance.total_amount is not None else 0.0,
                'order_timestamp': instance.created_at.isoformat() if instance.created_at else None,
                'updated_at': instance.updated_at.isoformat() if instance.updated_at else None,
                'delivery_address': instance.delivery_address,
                'notes': instance.notes,
                'products': []
            }

            # Add product details
            for item in instance.items.all():
                product_data = {
                    'product_id': item.product.id,
                    'name': item.product.name,
                    'batch_number': item.product.batch_number,
                    'quantity': float(item.quantity),
                    'unit_price': float(item.unit_price),
                    'subtotal': float(item.subtotal),
                    'animal_id': item.product.animal.animal_id if item.product.animal else None,
                    'animal_species': item.product.animal.species if item.product.animal else None,
                    'farmer_name': item.product.animal.farmer.username if item.product.animal else None,
                }
                qr_data['products'].append(product_data)

            qr_content = json.dumps(qr_data, indent=2)
            qr_filename = f"shop_order_qr_{instance.id}.png"

            # Create QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_content)
            qr.make(fit=True)

            # Create the image
            img = qr.make_image(fill_color="black", back_color="white")

            # Ensure the qr_codes directory exists
            qr_dir = os.path.join(settings.MEDIA_ROOT, 'qr_codes')
            os.makedirs(qr_dir, exist_ok=True)

            # Save the image
            filepath = os.path.join(qr_dir, qr_filename)
            img.save(filepath)

            # Update the instance with the relative path
            instance.qr_code = f"qr_codes/{qr_filename}"
            instance.save(update_fields=['qr_code'])

        except Exception as e:
            # Log the error but don't fail the order creation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to generate QR code for order {instance.id}: {str(e)}")


class JoinRequest(models.Model):
    """Model for handling join requests to processing units and shops"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ]

    REQUEST_TYPE_CHOICES = [
        ('processing_unit', 'Processing Unit'),
        ('shop', 'Shop'),
    ]

    # Request details
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='join_requests')
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Target entity
    processing_unit = models.ForeignKey(ProcessingUnit, null=True, blank=True, on_delete=models.CASCADE)
    shop = models.ForeignKey(Shop, null=True, blank=True, on_delete=models.CASCADE)

    # Request content
    requested_role = models.CharField(max_length=50)
    message = models.TextField(blank=True)
    qualifications = models.TextField(blank=True)

    # Response
    reviewed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_requests')
    response_message = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'processing_unit', 'shop']

    def __str__(self):
        entity_name = self.processing_unit.name if self.processing_unit else self.shop.name
        return f"{self.user.username} -> {entity_name} ({self.status})"


class Notification(models.Model):
    """Model for system notifications"""
    NOTIFICATION_TYPE_CHOICES = [
        ('join_request', 'Join Request'),
        ('join_approved', 'Join Request Approved'),
        ('join_rejected', 'Join Request Rejected'),
        ('invitation', 'User Invitation'),
        ('role_change', 'Role Changed'),
        ('profile_update', 'Profile Update Required'),
        ('verification', 'Account Verification'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPE_CHOICES)

    title = models.CharField(max_length=200)
    message = models.TextField()
    data = models.JSONField(default=dict, blank=True)  # Additional context data

    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    # Action URLs
    action_url = models.URLField(blank=True)
    action_text = models.CharField(max_length=50, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.notification_type} for {self.user.username}: {self.title}"


class Activity(models.Model):
    """Model for tracking farmer activities for the activity feed"""
    ACTIVITY_TYPE_CHOICES = [
        ('registration', 'Animal Registration'),
        ('transfer', 'Animal Transfer'),
        ('slaughter', 'Animal Slaughter'),
        ('health_update', 'Health Status Update'),
        ('weight_update', 'Weight Update'),
        ('vaccination', 'Vaccination'),
        ('other', 'Other Activity'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPE_CHOICES)

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)

    # Entity references
    entity_id = models.CharField(max_length=100, blank=True, null=True, help_text="ID of the related entity (animal, batch, etc.)")
    entity_type = models.CharField(max_length=50, blank=True, null=True, help_text="Type of entity (animal, batch, etc.)")

    # Additional metadata
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional activity metadata")
    target_route = models.CharField(max_length=200, blank=True, null=True, help_text="Route to navigate when activity is clicked")

    timestamp = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = 'Activities'
        indexes = [
            models.Index(fields=['-timestamp', 'user']),
            models.Index(fields=['activity_type']),
        ]

    def __str__(self):
        return f"{self.user.username}: {self.title} ({self.activity_type})"


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN DASHBOARD MODELS
# ══════════════════════════════════════════════════════════════════════════════

class SystemAlert(models.Model):
    """Model for system-wide alerts and notifications"""
    ALERT_TYPE_CHOICES = [
        ('info', 'Information'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical'),
        ('maintenance', 'Maintenance'),
    ]

    ALERT_CATEGORY_CHOICES = [
        ('system', 'System'),
        ('security', 'Security'),
        ('performance', 'Performance'),
        ('compliance', 'Compliance'),
        ('inventory', 'Inventory'),
        ('supply_chain', 'Supply Chain'),
    ]

    title = models.CharField(max_length=200)
    message = models.TextField()
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPE_CHOICES, default='info')
    category = models.CharField(max_length=20, choices=ALERT_CATEGORY_CHOICES, default='system')

    # Related entities
    processing_unit = models.ForeignKey(ProcessingUnit, on_delete=models.CASCADE, null=True, blank=True)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    # Alert metadata
    is_active = models.BooleanField(default=True)
    is_acknowledged = models.BooleanField(default=False)
    acknowledged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='acknowledged_alerts')
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    # Auto-resolution
    auto_resolve = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    # Additional data
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', 'alert_type']),
            models.Index(fields=['category', 'created_at']),
            models.Index(fields=['processing_unit', 'is_active']),
            models.Index(fields=['shop', 'is_active']),
        ]

    def __str__(self):
        return f"{self.alert_type.upper()}: {self.title}"


class PerformanceMetric(models.Model):
    """Model for tracking operational performance metrics"""
    METRIC_TYPE_CHOICES = [
        ('processing_efficiency', 'Processing Efficiency'),
        ('yield_rate', 'Yield Rate'),
        ('transfer_success', 'Transfer Success Rate'),
        ('inventory_turnover', 'Inventory Turnover'),
        ('order_fulfillment', 'Order Fulfillment Time'),
        ('quality_score', 'Quality Score'),
        ('compliance_rate', 'Compliance Rate'),
    ]

    name = models.CharField(max_length=100)
    metric_type = models.CharField(max_length=30, choices=METRIC_TYPE_CHOICES)
    value = models.DecimalField(max_digits=10, decimal_places=4)
    unit = models.CharField(max_length=20, blank=True, null=True)  # e.g., '%', 'kg', 'hours'

    # Context
    processing_unit = models.ForeignKey(ProcessingUnit, on_delete=models.CASCADE, null=True, blank=True)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, null=True, blank=True)

    # Time period
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()

    # Target and thresholds
    target_value = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    warning_threshold = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    critical_threshold = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)

    # Additional data
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-period_end']
        indexes = [
            models.Index(fields=['metric_type', 'period_end']),
            models.Index(fields=['processing_unit', 'metric_type']),
            models.Index(fields=['shop', 'metric_type']),
        ]

    def __str__(self):
        return f"{self.name}: {self.value} {self.unit or ''}"


class ComplianceAudit(models.Model):
    """Model for compliance audits and quality checks"""
    AUDIT_TYPE_CHOICES = [
        ('internal', 'Internal Audit'),
        ('external', 'External Audit'),
        ('regulatory', 'Regulatory Inspection'),
        ('quality_control', 'Quality Control Check'),
        ('traceability', 'Traceability Verification'),
    ]

    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    title = models.CharField(max_length=200)
    audit_type = models.CharField(max_length=20, choices=AUDIT_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')

    # Audit scope
    processing_unit = models.ForeignKey(ProcessingUnit, on_delete=models.CASCADE, null=True, blank=True)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, null=True, blank=True)

    # Audit details
    auditor = models.CharField(max_length=100, blank=True, null=True)
    auditor_organization = models.CharField(max_length=100, blank=True, null=True)
    scheduled_date = models.DateTimeField()
    completed_date = models.DateTimeField(null=True, blank=True)

    # Results
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Audit score (0-100)")
    findings = models.TextField(blank=True, null=True)
    recommendations = models.TextField(blank=True, null=True)

    # Follow-up
    follow_up_required = models.BooleanField(default=False)
    follow_up_date = models.DateTimeField(null=True, blank=True)
    follow_up_notes = models.TextField(blank=True, null=True)

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-scheduled_date']
        indexes = [
            models.Index(fields=['status', 'scheduled_date']),
            models.Index(fields=['audit_type', 'status']),
            models.Index(fields=['processing_unit', 'status']),
            models.Index(fields=['shop', 'status']),
        ]

    def __str__(self):
        return f"{self.audit_type}: {self.title} ({self.status})"


class Certification(models.Model):
    """Model for certifications and compliance documents"""
    CERT_TYPE_CHOICES = [
        ('haccp', 'HACCP'),
        ('iso22000', 'ISO 22000'),
        ('halal', 'Halal Certification'),
        ('organic', 'Organic Certification'),
        ('gmp', 'Good Manufacturing Practice'),
        ('traceability', 'Traceability Certification'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('pending', 'Pending Renewal'),
        ('suspended', 'Suspended'),
        ('revoked', 'Revoked'),
    ]

    name = models.CharField(max_length=200)
    cert_type = models.CharField(max_length=20, choices=CERT_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    # Associated entity
    processing_unit = models.ForeignKey(ProcessingUnit, on_delete=models.CASCADE, null=True, blank=True)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, null=True, blank=True)

    # Certification details
    issuing_authority = models.CharField(max_length=100)
    certificate_number = models.CharField(max_length=100, unique=True)
    issue_date = models.DateField()
    expiry_date = models.DateField()

    # Document storage
    certificate_file = models.FileField(upload_to='certificates/', null=True, blank=True)

    # Additional info
    notes = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-expiry_date']
        indexes = [
            models.Index(fields=['status', 'expiry_date']),
            models.Index(fields=['cert_type', 'status']),
            models.Index(fields=['processing_unit', 'status']),
            models.Index(fields=['shop', 'status']),
        ]

    def __str__(self):
        return f"{self.cert_type}: {self.name} ({self.status})"


class SystemHealth(models.Model):
    """Model for system health monitoring"""
    COMPONENT_CHOICES = [
        ('database', 'Database'),
        ('api', 'API Services'),
        ('file_storage', 'File Storage'),
        ('qr_generation', 'QR Code Generation'),
        ('email', 'Email Service'),
        ('notifications', 'Notification System'),
        ('backup', 'Backup System'),
    ]

    STATUS_CHOICES = [
        ('healthy', 'Healthy'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
        ('offline', 'Offline'),
    ]

    component = models.CharField(max_length=20, choices=COMPONENT_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='healthy')

    # Metrics
    response_time = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True, help_text="Response time in seconds")
    uptime_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Uptime percentage")

    # Status details
    message = models.TextField(blank=True, null=True)
    last_check = models.DateTimeField(default=timezone.now)
    next_check = models.DateTimeField(null=True, blank=True)

    # Alert thresholds
    warning_threshold = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    critical_threshold = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ['component']
        ordering = ['component']

    def __str__(self):
        return f"{self.component}: {self.status}"


class SecurityLog(models.Model):
    """Model for security events and access logs"""
    EVENT_TYPE_CHOICES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('failed_login', 'Failed Login'),
        ('password_change', 'Password Change'),
        ('permission_change', 'Permission Change'),
        ('suspicious_activity', 'Suspicious Activity'),
        ('data_access', 'Data Access'),
        ('api_access', 'API Access'),
        ('file_access', 'File Access'),
    ]

    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='security_events')
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='low')

    # Event details
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)

    # Related entities
    processing_unit = models.ForeignKey(ProcessingUnit, on_delete=models.SET_NULL, null=True, blank=True)
    shop = models.ForeignKey(Shop, on_delete=models.SET_NULL, null=True, blank=True)

    # Additional context
    resource = models.CharField(max_length=200, blank=True, null=True, help_text="Resource that was accessed")
    action = models.CharField(max_length=100, blank=True, null=True, help_text="Action performed")

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)

    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['event_type', 'timestamp']),
            models.Index(fields=['severity', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
        ]

    def __str__(self):
        user_info = self.user.username if self.user else 'Anonymous'
        return f"{self.event_type} by {user_info} at {self.timestamp}"


class TransferRequest(models.Model):
    """Model for pending transfer requests that need admin approval"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]

    REQUEST_TYPE_CHOICES = [
        ('animal_transfer', 'Animal Transfer'),
        ('product_transfer', 'Product Transfer'),
        ('part_transfer', 'Slaughter Part Transfer'),
    ]

    # Request details
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Entities involved
    from_processing_unit = models.ForeignKey(ProcessingUnit, on_delete=models.CASCADE, related_name='outgoing_transfers')
    to_processing_unit = models.ForeignKey(ProcessingUnit, on_delete=models.CASCADE, related_name='incoming_transfers')

    # Requestor and approver
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transfer_requests')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_transfers')
    approved_at = models.DateTimeField(null=True, blank=True)

    # Transfer details
    animal = models.ForeignKey(Animal, on_delete=models.CASCADE, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True)
    slaughter_parts = models.ManyToManyField(SlaughterPart, blank=True)

    # Quantities and details
    quantity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True, null=True)

    # Approval workflow
    approval_required = models.BooleanField(default=True)
    priority = models.CharField(max_length=10, choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('urgent', 'Urgent')], default='medium')

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['request_type', 'status']),
            models.Index(fields=['from_processing_unit', 'status']),
            models.Index(fields=['to_processing_unit', 'status']),
        ]

    def __str__(self):
        return f"{self.request_type} from {self.from_processing_unit.name} to {self.to_processing_unit.name} ({self.status})"


class ProductInfo(models.Model):
    """Aggregated model for product information display - combines product, animal, and related data"""
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='info')

    # Product basic info (denormalized for performance)
    product_name = models.CharField(max_length=200)
    product_type = models.CharField(max_length=20)
    batch_number = models.CharField(max_length=100)
    weight = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    weight_unit = models.CharField(max_length=10, null=True, blank=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    description = models.TextField(blank=True, null=True)
    manufacturer = models.CharField(max_length=200, blank=True, null=True)
    qr_code_url = models.CharField(max_length=500, blank=True, null=True)

    # Processing unit info
    processing_unit_name = models.CharField(max_length=200, null=True, blank=True)
    processing_unit_location = models.CharField(max_length=200, null=True, blank=True)

    # Category info
    category_name = models.CharField(max_length=100, null=True, blank=True)

    # Animal info (if exists)
    animal_id = models.CharField(max_length=50, null=True, blank=True)
    animal_name = models.CharField(max_length=100, null=True, blank=True)
    animal_species = models.CharField(max_length=20, null=True, blank=True)
    farmer_username = models.CharField(max_length=150, null=True, blank=True)
    animal_live_weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    animal_slaughtered = models.BooleanField(default=False)
    animal_slaughtered_at = models.DateTimeField(null=True, blank=True)
    animal_transferred_at = models.DateTimeField(null=True, blank=True)
    animal_transferred_to_name = models.CharField(max_length=200, null=True, blank=True)

    # Timeline events (stored as JSON)
    timeline_events = models.JSONField(default=list, blank=True)

    # Inventory, receipts, orders counts
    inventory_count = models.IntegerField(default=0)
    receipts_count = models.IntegerField(default=0)
    orders_count = models.IntegerField(default=0)

    # Carcass measurement data (if exists)
    carcass_measurement_data = models.JSONField(null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"ProductInfo for {self.product_name}"

    def update_from_product(self):
        """Update this ProductInfo instance from the related Product"""
        product = self.product

        # Basic product info
        self.product_name = product.name
        self.product_type = product.product_type
        self.batch_number = product.batch_number
        self.weight = product.weight
        self.weight_unit = product.weight_unit
        self.quantity = product.quantity
        self.price = product.price
        self.description = product.description
        self.manufacturer = product.manufacturer
        self.qr_code_url = product.qr_code

        # Processing unit info
        if product.processing_unit:
            self.processing_unit_name = product.processing_unit.name
            self.processing_unit_location = product.processing_unit.location

        # Category info
        if product.category:
            self.category_name = product.category.name

        # Animal info
        if product.animal:
            animal = product.animal
            self.animal_id = animal.animal_id
            self.animal_name = animal.animal_name
            self.animal_species = animal.species
            self.farmer_username = animal.farmer.username
            self.animal_live_weight = getattr(animal, 'live_weight', None)
            self.animal_slaughtered = animal.slaughtered
            self.animal_slaughtered_at = animal.slaughtered_at
            self.animal_transferred_at = animal.transferred_at
            if animal.transferred_to:
                self.animal_transferred_to_name = animal.transferred_to.name

        # Build timeline events
        timeline = []

        # Product creation event
        timeline.append({
            'stage': 'Product Created',
            'timestamp': product.created_at.isoformat(),
            'location': self.processing_unit_name or 'Unknown',
            'action': f'Product {self.product_name} created',
            'details': {
                'Product Type': self.product_type,
                'Batch Number': self.batch_number,
                'Weight': f"{self.weight} {self.weight_unit}" if self.weight else 'Not recorded',
                'Quantity': f"{self.quantity} {self.weight_unit}" if self.quantity else 'Not recorded'
            }
        })

        # Add animal-related events if animal exists
        if product.animal:
            # Animal registration
            timeline.append({
                'stage': 'Source Animal',
                'timestamp': product.animal.created_at.isoformat(),
                'location': self.farmer_username,
                'action': f'Animal {self.animal_id} registered',
                'details': {
                    'Species': self.animal_species,
                    'Farmer': self.farmer_username,
                    'Weight': 'Not recorded'  # Temporarily disable weight display
                }
            })

            # Slaughter event if applicable
            if self.animal_slaughtered and self.animal_slaughtered_at:
                timeline.append({
                    'stage': 'Slaughter',
                    'timestamp': self.animal_slaughtered_at.isoformat(),
                    'location': 'Processing Unit',
                    'action': f'Animal {self.animal_id} slaughtered',
                    'details': {
                        'Species': self.animal_species,
                        'Slaughter Date': self.animal_slaughtered_at.strftime('%Y-%m-%d %H:%M')
                    }
                })

            # Transfer event if applicable
            if self.animal_transferred_at:
                timeline.append({
                    'stage': 'Transfer',
                    'timestamp': self.animal_transferred_at.isoformat(),
                    'location': self.animal_transferred_to_name or 'Unknown',
                    'action': f'Animal transferred to {self.animal_transferred_to_name or "processing unit"}',
                    'details': {
                        'From': self.farmer_username,
                        'To': self.animal_transferred_to_name or 'Processing Unit',
                        'Transfer Mode': 'Whole carcass' if not hasattr(product.animal, 'slaughter_parts') or not product.animal.slaughter_parts.exists() else 'Parts'
                    }
                })

        # Sort timeline by timestamp
        timeline.sort(key=lambda x: x['timestamp'])
        self.timeline_events = timeline

        # Count related records
        self.inventory_count = Inventory.objects.filter(product=product).count()
        self.receipts_count = Receipt.objects.filter(product=product).count()
        self.orders_count = OrderItem.objects.filter(product=product).count()

        # Carcass measurement data
        if product.animal and hasattr(product.animal, 'carcass_measurement'):
            carcass_measurement = product.animal.carcass_measurement
            self.carcass_measurement_data = {
                'carcass_type': carcass_measurement.carcass_type,
                'measurements': carcass_measurement.get_all_measurements() if hasattr(carcass_measurement, 'get_all_measurements') else []
            }

        self.updated_at = timezone.now()
        self.save()


class BackupSchedule(models.Model):
    """Model for system backup scheduling"""
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('manual', 'Manual Only'),
    ]

    BACKUP_TYPE_CHOICES = [
        ('full', 'Full Backup'),
        ('incremental', 'Incremental Backup'),
        ('differential', 'Differential Backup'),
    ]

    name = models.CharField(max_length=100)
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='daily')
    backup_type = models.CharField(max_length=15, choices=BACKUP_TYPE_CHOICES, default='full')

    # Schedule details
    scheduled_time = models.TimeField()
    last_run = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField(null=True, blank=True)

    # Backup scope
    include_database = models.BooleanField(default=True)
    include_files = models.BooleanField(default=True)
    include_media = models.BooleanField(default=True)

    # Retention
    retention_days = models.PositiveIntegerField(default=30)

    # Status
    is_active = models.BooleanField(default=True)
    last_status = models.CharField(max_length=20, choices=[('success', 'Success'), ('failed', 'Failed'), ('running', 'Running')], null=True, blank=True)

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['next_run']

    def __str__(self):
        return f"{self.name} ({self.frequency} {self.backup_type})"


class Sale(models.Model):
    """Model for sales transactions at shops"""
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('mobile_money', 'Mobile Money'),
    ]

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='sales')
    sold_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sales_made')
    customer_name = models.CharField(max_length=200, blank=True, null=True)
    customer_phone = models.CharField(max_length=20, blank=True, null=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash')
    created_at = models.DateTimeField(default=timezone.now)
    qr_code = models.CharField(max_length=500, blank=True)

    def __str__(self):
        return f"Sale #{self.id} - {self.shop.name} - {self.total_amount}"

    class Meta:
        ordering = ['-created_at']


class SaleItem(models.Model):
    """Model for individual items in a sale"""
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

    def save(self, *args, **kwargs):
        # Auto-calculate subtotal
        self.subtotal = self.quantity * self.unit_price
        super().save(*args, **kwargs)


@receiver(post_save, sender=Sale)
def generate_sale_qr_code(sender, instance, created, **kwargs):
    """Generate QR code for new sales that links to the sale info page"""
    if created and not instance.qr_code:
        try:
            # Generate the URL for the sale info HTML page
            url = f"{getattr(settings, 'SITE_URL', 'http://localhost:8000')}/api/v2/sale-info/view/{instance.id}/"

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
            filename = f"sale_qr_{instance.id}.png"
            filepath = os.path.join(qr_dir, filename)
            img.save(filepath)

            # Update the instance with the relative path
            instance.qr_code = f"qr_codes/{filename}"
            instance.save(update_fields=['qr_code'])

        except Exception as e:
            # Log the error but don't fail the sale creation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to generate QR code for sale {instance.id}: {str(e)}")


@receiver(post_save, sender=SaleItem)
def update_inventory_on_sale(sender, instance, created, **kwargs):
    """
    DISABLED: Inventory updates are now handled synchronously in the SaleViewSet.create() method.
    This signal is kept for backward compatibility but does nothing.
    """
    pass
