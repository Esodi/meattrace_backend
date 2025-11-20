from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
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
        ('Farmer', 'Farmer'),
        ('Processor', 'Processor'),
        ('ShopOwner', 'Shop Owner'),
        ('Admin', 'Administrator'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Farmer')
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
    """Create UserProfile when a new User is created"""
    if created:
        # If the user is a staff/superuser (created via createsuperuser or admin tools),
        # create the profile with the Admin role so they are shown correctly in admin dashboards.
        role = 'Admin' if (getattr(instance, 'is_staff', False) or getattr(instance, 'is_superuser', False)) else 'Farmer'
        UserProfile.objects.create(user=instance, role=role)
        # Note: existing registration code can still override this if needed.


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
    remaining_weight = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0)], null=True, blank=True, help_text="Remaining weight available for product creation")
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

    # Rejection fields
    REJECTION_STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('rejected', 'Rejected'),
        ('appealed', 'Appealed'),
        ('resolved', 'Resolved'),
    ]
    rejection_status = models.CharField(max_length=20, choices=REJECTION_STATUS_CHOICES, blank=True, null=True, help_text="Current rejection status")
    rejection_reason_category = models.CharField(max_length=20, blank=True, null=True, help_text="Category of rejection reason")
    rejection_reason_specific = models.CharField(max_length=30, blank=True, null=True, help_text="Specific rejection reason")
    rejection_notes = models.TextField(blank=True, null=True, help_text="Additional notes about the rejection")
    rejected_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='rejected_animals', help_text="User who rejected the animal")
    rejected_at = models.DateTimeField(null=True, blank=True, help_text="Date and time when the animal was rejected")

    # Appeal fields
    APPEAL_STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('denied', 'Denied'),
        ('resolved', 'Resolved'),
    ]
    appeal_status = models.CharField(max_length=20, choices=APPEAL_STATUS_CHOICES, blank=True, null=True, help_text="Current appeal status")
    appeal_notes = models.TextField(blank=True, null=True, help_text="Notes about the appeal")
    appealed_at = models.DateTimeField(null=True, blank=True, help_text="Date and time when the appeal was submitted")
    appeal_resolved_at = models.DateTimeField(null=True, blank=True, help_text="Date and time when the appeal was resolved")

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

        # Ensure animal_id exists only if not manually set
        if not self.animal_id:
            self.animal_id = self._generate_animal_id()
        
        # Initialize remaining_weight if not set
        if self.remaining_weight is None and self.live_weight is not None:
            self.remaining_weight = self.live_weight

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
        Determine the animal's lifecycle status based on five distinct categories:
        1. REJECTED - Animal was rejected by processing unit and returned to farmer
        2. HEALTHY - Alive, in good condition, no transfers or processing
        3. SLAUGHTERED - Processed and no longer alive (but NOT transferred)
        4. TRANSFERRED - Entire body/all parts completely transferred
        5. SEMI-TRANSFERRED - Partially transferred (some parts moved, others remain)
        
        Priority order:
        1. Check rejection status first (highest priority)
        2. Check transfer status (whole animal or all parts)
        3. Check for partial transfers
        4. Check if slaughtered (but not transferred)
        5. Default to healthy
        """
        # Priority 1: Check if animal is rejected (highest priority)
        if self.rejection_status == 'rejected':
            return 'REJECTED'
        
        # Priority 2: Check if whole animal is transferred
        if self.transferred_to is not None:
            return 'TRANSFERRED'
        
        # Priority 3: Check for partial or complete part transfers
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
        
        # Priority 4: Check if slaughtered (but not transferred)
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
    part_id = models.CharField(max_length=50, unique=True, editable=False, default='', help_text="Auto-generated unique part identifier")
    PART_CHOICES = [
        ('whole_carcass', 'Whole Carcass'),
        ('left_side', 'Left Side'),
        ('right_side', 'Right Side'),
        ('left_carcass', 'Left Carcass'),
        ('right_carcass', 'Right Carcass'),
        ('head', 'Head'),
        ('feet', 'Feet'),
        ('internal_organs', 'Internal Organs'),
        ('torso', 'Torso'),
        ('front_legs', 'Front Legs'),
        ('hind_legs', 'Hind Legs'),
    ]

    animal = models.ForeignKey(Animal, on_delete=models.CASCADE, related_name='slaughter_parts')
    part_type = models.CharField(max_length=20, choices=PART_CHOICES, default='whole_carcass')
    weight = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)], help_text="Weight of this part in kg")
    remaining_weight = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)], null=True, blank=True, help_text="Remaining weight available for product creation")
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

    # Rejection fields
    REJECTION_STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('rejected', 'Rejected'),
        ('appealed', 'Appealed'),
        ('resolved', 'Resolved'),
    ]
    rejection_status = models.CharField(max_length=20, choices=REJECTION_STATUS_CHOICES, blank=True, null=True, help_text="Current rejection status")
    rejection_reason_category = models.CharField(max_length=20, blank=True, null=True, help_text="Category of rejection reason")
    rejection_reason_specific = models.CharField(max_length=30, blank=True, null=True, help_text="Specific rejection reason")
    rejection_notes = models.TextField(blank=True, null=True, help_text="Additional notes about the rejection")
    rejected_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='rejected_parts', help_text="User who rejected the part")
    rejected_at = models.DateTimeField(null=True, blank=True, help_text="Date and time when the part was rejected")

    # Appeal fields
    APPEAL_STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('denied', 'Denied'),
        ('resolved', 'Resolved'),
    ]
    appeal_status = models.CharField(max_length=20, choices=APPEAL_STATUS_CHOICES, blank=True, null=True, help_text="Current appeal status")
    appeal_notes = models.TextField(blank=True, null=True, help_text="Notes about the appeal")
    appealed_at = models.DateTimeField(null=True, blank=True, help_text="Date and time when the appeal was submitted")
    appeal_resolved_at = models.DateTimeField(null=True, blank=True, help_text="Date and time when the appeal was resolved")

    def __str__(self):
        return f"{self.part_type} of {self.animal.animal_id} ({self.weight} {self.weight_unit})"

    class Meta:
        unique_together = ['animal', 'part_type']  # Prevent duplicate parts for same animal

    def save(self, *args, **kwargs):
        # Ensure part_id exists
        if not self.part_id:
            self.part_id = self._generate_part_id()
        # Initialize remaining_weight if not set
        if self.remaining_weight is None:
            self.remaining_weight = self.weight
        super().save(*args, **kwargs)

    def _generate_part_id(self):
        """Generate a unique part ID using UUID"""
        return f"PART_{uuid.uuid4().hex[:12].upper()}"


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
    head_weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Weight of head")
    torso_weight = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)], null=True, blank=True, help_text="Weight of torso")
    # Split carcass fields (aligned with frontend naming)
    left_carcass_weight = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)], null=True, blank=True, help_text="Weight of left carcass")
    right_carcass_weight = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)], null=True, blank=True, help_text="Weight of right carcass")
    feet_weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Weight of feet")
    whole_carcass_weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Weight of whole carcass")
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
            if (self.left_carcass_weight is not None and self.right_carcass_weight is not None and
                self.feet_weight is not None and self.organs_weight is not None):
                return (self.left_carcass_weight + self.right_carcass_weight +
                        self.feet_weight + self.organs_weight)
        return None

    def clean(self):
        """Validate carcass measurement data"""
        from django.core.exceptions import ValidationError

        # Validate all weights are positive and within realistic ranges
        weight_fields = ['head_weight', 'torso_weight', 'left_carcass_weight',
                        'right_carcass_weight', 'feet_weight', 'whole_carcass_weight', 'organs_weight']
        for field_name in weight_fields:
            weight = getattr(self, field_name)
            if weight is not None:
                if weight <= 0:
                    raise ValidationError(f"{field_name.replace('_', ' ').title()} must be positive.")
                # Check for unrealistic weights (too large for typical livestock)
                if weight > 2000:
                    raise ValidationError(f"{field_name.replace('_', ' ').title()} seems unusually large. Please verify the measurement.")

        # Validate required fields based on carcass_type
        if self.carcass_type == 'whole':
            if self.whole_carcass_weight is None:
                raise ValidationError("For whole carcass, whole_carcass_weight is required.")
        elif self.carcass_type == 'split':
            # For split carcass, left and right carcass weights are required
            if self.left_carcass_weight is None or self.right_carcass_weight is None:
                raise ValidationError("For split carcass, both left_carcass_weight and right_carcass_weight are required.")

            # Validate that total weight makes sense (not too small for any animal)
            total_weight = 0.0
            if self.head_weight: total_weight += self.head_weight
            if self.torso_weight: total_weight += self.torso_weight
            if self.left_carcass_weight: total_weight += self.left_carcass_weight
            if self.right_carcass_weight: total_weight += self.right_carcass_weight
            if self.feet_weight: total_weight += self.feet_weight
            if self.organs_weight: total_weight += self.organs_weight

            if total_weight > 0 and total_weight < 0.5:
                raise ValidationError("Total carcass weight seems too small. Please verify measurements.")

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
    quantity_received = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], default=0, help_text="Quantity actually received by shop")
    
    # Rejection fields for products
    REJECTION_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('rejected', 'Rejected'),
    ]
    
    rejection_status = models.CharField(max_length=20, choices=REJECTION_STATUS_CHOICES, blank=True, null=True, help_text="Current rejection status")
    rejection_reason = models.TextField(blank=True, null=True, help_text="Reason for rejection")
    quantity_rejected = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], default=0, help_text="Quantity rejected by shop")
    rejected_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='rejected_products', help_text="User who rejected the product")
    rejected_at = models.DateTimeField(null=True, blank=True, help_text="Date and time when the product was rejected")

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


class NotificationTemplate(models.Model):
    """Model for notification templates with variable substitution"""
    TEMPLATE_TYPE_CHOICES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('push', 'Push Notification'),
        ('in_app', 'In-App Notification'),
    ]

    name = models.CharField(max_length=100, unique=True)
    template_type = models.CharField(max_length=10, choices=TEMPLATE_TYPE_CHOICES)
    subject = models.CharField(max_length=200, blank=True, help_text="Email subject (for email templates)")
    content = models.TextField(help_text="Template content with {{variable}} placeholders")
    variables = models.JSONField(default=list, help_text="List of available variables for this template")

    # Template metadata
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_templates')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.template_type}: {self.name}"

    def render_content(self, context):
        """Render template content with variable substitution"""
        import re
        content = self.content
        for var in self.variables:
            placeholder = f"{{{{{var}}}}}"
            value = context.get(var, '')
            content = content.replace(placeholder, str(value))
        return content

    def render_subject(self, context):
        """Render email subject with variable substitution"""
        if not self.subject:
            return ""
        import re
        subject = self.subject
        for var in self.variables:
            placeholder = f"{{{{{var}}}}}"
            value = context.get(var, '')
            subject = subject.replace(placeholder, str(value))
        return subject


class NotificationChannel(models.Model):
    """Model for notification delivery channels"""
    CHANNEL_TYPE_CHOICES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('push', 'Push Notification'),
        ('in_app', 'In-App Notification'),
    ]

    name = models.CharField(max_length=100, unique=True)
    channel_type = models.CharField(max_length=10, choices=CHANNEL_TYPE_CHOICES)
    is_active = models.BooleanField(default=True)

    # Channel configuration
    config = models.JSONField(default=dict, help_text="Channel-specific configuration (API keys, endpoints, etc.)")

    # Rate limiting
    rate_limit_per_minute = models.PositiveIntegerField(default=60)
    rate_limit_per_hour = models.PositiveIntegerField(default=1000)
    rate_limit_per_day = models.PositiveIntegerField(default=10000)

    # Provider settings
    provider_name = models.CharField(max_length=100, blank=True, help_text="Name of the service provider")
    provider_config = models.JSONField(default=dict, help_text="Provider-specific configuration")

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.channel_type}: {self.name}"

    def is_rate_limited(self, user=None):
        """Check if channel is rate limited for a user"""
        from django.utils import timezone
        from datetime import timedelta

        now = timezone.now()
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)

        base_queryset = NotificationDelivery.objects.filter(
            channel=self,
            created_at__gte=day_ago
        )

        if user:
            base_queryset = base_queryset.filter(recipient=user)

        # Check rate limits
        minute_count = base_queryset.filter(created_at__gte=minute_ago).count()
        hour_count = base_queryset.filter(created_at__gte=hour_ago).count()
        day_count = base_queryset.count()

        return (
            minute_count >= self.rate_limit_per_minute or
            hour_count >= self.rate_limit_per_hour or
            day_count >= self.rate_limit_per_day
        )


class NotificationDelivery(models.Model):
    """Model for tracking notification delivery attempts and status"""
    DELIVERY_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('retrying', 'Retrying'),
        ('cancelled', 'Cancelled'),
    ]

    notification = models.ForeignKey('Notification', on_delete=models.CASCADE, related_name='deliveries')
    channel = models.ForeignKey(NotificationChannel, on_delete=models.CASCADE)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notification_deliveries')

    # Delivery details
    status = models.CharField(max_length=20, choices=DELIVERY_STATUS_CHOICES, default='pending')
    external_id = models.CharField(max_length=255, blank=True, help_text="External service message ID")
    error_message = models.TextField(blank=True, help_text="Error message if delivery failed")

    # Retry logic
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=3)
    next_retry_at = models.DateTimeField(null=True, blank=True)

    # Timing
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    metadata = models.JSONField(default=dict, blank=True, help_text="Delivery-specific metadata")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['notification', 'status']),
            models.Index(fields=['channel', 'status']),
            models.Index(fields=['recipient', 'status']),
            models.Index(fields=['status', 'next_retry_at']),
        ]

    def __str__(self):
        return f"{self.notification.title} -> {self.recipient.username} via {self.channel.name} ({self.status})"

    def can_retry(self):
        """Check if delivery can be retried"""
        return (
            self.status in ['failed', 'pending'] and
            self.retry_count < self.max_retries and
            self.notification.expires_at is None or timezone.now() < self.notification.expires_at
        )

    def mark_sent(self, external_id=None):
        """Mark delivery as sent"""
        self.status = 'sent'
        self.sent_at = timezone.now()
        if external_id:
            self.external_id = external_id
        self.save()

    def mark_delivered(self):
        """Mark delivery as delivered"""
        self.status = 'delivered'
        self.delivered_at = timezone.now()
        self.save()

    def mark_failed(self, error_message=None):
        """Mark delivery as failed"""
        self.status = 'failed'
        self.failed_at = timezone.now()
        if error_message:
            self.error_message = error_message
        self.retry_count += 1

        # Schedule next retry if possible
        if self.can_retry():
            self.status = 'retrying'
            # Exponential backoff: 5 minutes * 2^retry_count
            delay_minutes = 5 * (2 ** self.retry_count)
            self.next_retry_at = timezone.now() + timezone.timedelta(minutes=delay_minutes)

        self.save()


class NotificationRateLimit(models.Model):
    """Model for tracking rate limiting per user/channel"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rate_limits')
    channel = models.ForeignKey(NotificationChannel, on_delete=models.CASCADE)

    # Rate limit counters
    minute_count = models.PositiveIntegerField(default=0)
    hour_count = models.PositiveIntegerField(default=0)
    day_count = models.PositiveIntegerField(default=0)

    # Reset timestamps
    minute_reset = models.DateTimeField(default=timezone.now)
    hour_reset = models.DateTimeField(default=timezone.now)
    day_reset = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ['user', 'channel']
        indexes = [
            models.Index(fields=['user', 'channel']),
            models.Index(fields=['minute_reset']),
            models.Index(fields=['hour_reset']),
            models.Index(fields=['day_reset']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.channel.name} rate limits"

    def reset_if_needed(self):
        """Reset counters if time windows have passed"""
        now = timezone.now()

        if now >= self.minute_reset + timezone.timedelta(minutes=1):
            self.minute_count = 0
            self.minute_reset = now

        if now >= self.hour_reset + timezone.timedelta(hours=1):
            self.hour_count = 0
            self.hour_reset = now

        if now >= self.day_reset + timezone.timedelta(days=1):
            self.day_count = 0
            self.day_reset = now

        self.save()

    def increment_and_check(self):
        """Increment counters and check if limit exceeded"""
        self.reset_if_needed()

        self.minute_count += 1
        self.hour_count += 1
        self.day_count += 1
        self.save()

        return (
            self.minute_count > self.channel.rate_limit_per_minute or
            self.hour_count > self.channel.rate_limit_per_hour or
            self.day_count > self.channel.rate_limit_per_day
        )


class NotificationSchedule(models.Model):
    """Model for scheduling notifications"""
    SCHEDULE_TYPE_CHOICES = [
        ('one_time', 'One Time'),
        ('recurring', 'Recurring'),
    ]

    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    title = models.CharField(max_length=200)
    schedule_type = models.CharField(max_length=10, choices=SCHEDULE_TYPE_CHOICES, default='one_time')

    # Recipients
    recipient_users = models.ManyToManyField(User, blank=True, related_name='scheduled_notifications')
    recipient_groups = models.JSONField(default=list, blank=True, help_text="Groups to send to (e.g., ['farmers', 'processors'])")

    # Content
    notification_type = models.CharField(max_length=30, choices=[
        ('join_request', 'Join Request'),
        ('join_approved', 'Join Request Approved'),
        ('join_rejected', 'Join Request Rejected'),
        ('invitation', 'User Invitation'),
        ('role_change', 'Role Changed'),
        ('profile_update', 'Profile Update Required'),
        ('verification', 'Account Verification'),
        ('animal_rejected', 'Animal Rejected'),
        ('part_rejected', 'Slaughter Part Rejected'),
        ('appeal_submitted', 'Appeal Submitted'),
        ('appeal_approved', 'Appeal Approved'),
        ('appeal_denied', 'Appeal Denied'),
        ('system_alert', 'System Alert'),
        ('maintenance', 'Maintenance Notice'),
        ('custom', 'Custom Notification'),
    ])
    title_template = models.CharField(max_length=200)
    message_template = models.TextField()
    template_variables = models.JSONField(default=dict, blank=True)

    # Scheduling
    scheduled_at = models.DateTimeField(null=True, blank=True)
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    # Channels
    channels = models.ManyToManyField(NotificationChannel, blank=True)

    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_schedules')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-scheduled_at']

    def __str__(self):
        return f"{self.schedule_type}: {self.title}"

    def should_send_now(self):
        """Check if notification should be sent now"""
        if not self.is_active:
            return False

        now = timezone.now()

        if self.schedule_type == 'one_time':
            return self.scheduled_at and now >= self.scheduled_at
        elif self.schedule_type == 'recurring':
            # For recurring, check if it's time based on frequency
            # This is a simplified implementation
            if self.frequency == 'daily':
                return now.hour == self.scheduled_at.hour and now.minute == self.scheduled_at.minute
            elif self.frequency == 'weekly':
                return (now.weekday() == self.scheduled_at.weekday() and
                       now.hour == self.scheduled_at.hour and
                       now.minute == self.scheduled_at.minute)
            elif self.frequency == 'monthly':
                return (now.day == self.scheduled_at.day and
                       now.hour == self.scheduled_at.hour and
                       now.minute == self.scheduled_at.minute)

        return False


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
        ('animal_rejected', 'Animal Rejected'),
        ('part_rejected', 'Slaughter Part Rejected'),
        ('appeal_submitted', 'Appeal Submitted'),
        ('appeal_approved', 'Appeal Approved'),
        ('appeal_denied', 'Appeal Denied'),
        ('system_alert', 'System Alert'),
        ('maintenance', 'Maintenance Notice'),
        ('custom', 'Custom Notification'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    ACTION_TYPE_CHOICES = [
        ('none', 'No Action'),
        ('view', 'View Details'),
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('respond', 'Respond'),
        ('appeal', 'Appeal'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPE_CHOICES)

    title = models.CharField(max_length=200)
    message = models.TextField()
    data = models.JSONField(default=dict, blank=True)  # Additional context data

    # New fields for enhanced notification system
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    is_dismissed = models.BooleanField(default=False)
    dismissed_at = models.DateTimeField(null=True, blank=True)
    action_type = models.CharField(max_length=20, choices=ACTION_TYPE_CHOICES, default='none')
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    group_key = models.CharField(max_length=100, blank=True, help_text="Groups related notifications together")
    is_batch_notification = models.BooleanField(default=False, help_text="Indicates if this is part of a batch notification")

    # Template and scheduling
    template = models.ForeignKey(NotificationTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    schedule = models.ForeignKey(NotificationSchedule, on_delete=models.SET_NULL, null=True, blank=True)

    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    # Action URLs
    action_url = models.URLField(blank=True)
    action_text = models.CharField(max_length=50, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['user', 'is_dismissed']),
            models.Index(fields=['user', 'is_archived']),
            models.Index(fields=['priority', 'created_at']),
            models.Index(fields=['group_key', 'created_at']),
            models.Index(fields=['notification_type', 'created_at']),
        ]

    def __str__(self):
        return f"{self.notification_type} for {self.user.username}: {self.title}"

    def send_via_channels(self, channels=None):
        """Send notification via specified channels"""
        from .utils.notification_service import NotificationService

        if channels is None:
            # Default channels based on notification type and priority
            channels = self._get_default_channels()

        for channel in channels:
            NotificationService.send_via_channel(self, channel)

    def _get_default_channels(self):
        """Get default channels for this notification"""
        channels = []

        # Always include in-app
        try:
            in_app_channel = NotificationChannel.objects.get(channel_type='in_app', is_active=True)
            channels.append(in_app_channel)
        except NotificationChannel.DoesNotExist:
            pass

        # Add email for high priority notifications
        if self.priority in ['high', 'urgent']:
            try:
                email_channel = NotificationChannel.objects.get(channel_type='email', is_active=True)
                channels.append(email_channel)
            except NotificationChannel.DoesNotExist:
                pass

        # Add SMS for urgent notifications
        if self.priority == 'urgent':
            try:
                sms_channel = NotificationChannel.objects.get(channel_type='sms', is_active=True)
                channels.append(sms_channel)
            except NotificationChannel.DoesNotExist:
                pass

        return channels


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

        # 1. Animal Registration (if exists)
        if product.animal:
            animal = product.animal
            timeline.append({
                'stage': 'Animal Registration',
                'category': 'farmer',
                'timestamp': animal.created_at.isoformat(),
                'location': f'Farm - {self.farmer_username}',
                'action': f'Animal {self.animal_id} registered',
                'icon': 'fa-clipboard-list',
                'details': {
                    'Animal ID': self.animal_id or 'Unknown',
                    'Animal Name': self.animal_name or 'Not named',
                    'Species': self.animal_species or 'Unknown',
                    'Farmer': self.farmer_username or 'Unknown',
                    'Age': f'{animal.age} months' if animal.age else 'Not recorded',
                    'Weight': f'{animal.weight} kg' if animal.weight else 'Not recorded'
                }
            })
            
            # 2. Animal Transfer
            if self.animal_transferred_at and self.animal_transferred_to_name:
                timeline.append({
                    'stage': 'Animal Transfer',
                    'category': 'logistics',
                    'timestamp': self.animal_transferred_at.isoformat(),
                    'location': self.animal_transferred_to_name,
                    'action': f'Animal transferred to processing unit',
                    'icon': 'fa-truck',
                    'details': {
                        'From': f'Farm - {self.farmer_username}',
                        'To': self.animal_transferred_to_name,
                        'Animal ID': self.animal_id
                    }
                })
            
            # 3. Slaughter
            if self.animal_slaughtered and self.animal_slaughtered_at:
                timeline.append({
                    'stage': 'Slaughter',
                    'category': 'processing',
                    'timestamp': self.animal_slaughtered_at.isoformat(),
                    'location': self.animal_transferred_to_name or 'Processing Unit',
                    'action': f'Animal slaughtered',
                    'icon': 'fa-cut',
                    'details': {
                        'Animal ID': self.animal_id,
                        'Species': self.animal_species,
                        'Slaughter Date': self.animal_slaughtered_at.strftime('%Y-%m-%d %H:%M')
                    }
                })

        # 4. Product Creation
        timeline.append({
            'stage': 'Product Creation',
            'category': 'processing',
            'timestamp': product.created_at.isoformat(),
            'location': self.processing_unit_name or 'Processing Unit',
            'action': f'Product "{self.product_name}" created',
            'icon': 'fa-box',
            'details': {
                'Product Name': self.product_name,
                'Batch Number': self.batch_number,
                'Product Type': self.product_type,
                'Quantity': f"{self.quantity} {self.weight_unit}" if self.quantity else 'Not recorded',
                'Weight': f"{self.weight} {self.weight_unit}" if self.weight else 'Not recorded'
            }
        })
        
        # 5. Product Transfer (if transferred)
        if product.transferred_at and product.transferred_to:
            timeline.append({
                'stage': 'Product Transfer',
                'category': 'logistics',
                'timestamp': product.transferred_at.isoformat(),
                'location': product.transferred_to.name,
                'action': f'Product transferred to shop',
                'icon': 'fa-truck-loading',
                'details': {
                    'From': self.processing_unit_name or 'Processing Unit',
                    'To': product.transferred_to.name,
                    'Batch': self.batch_number,
                    'Quantity': f"{self.quantity} {self.weight_unit}"
                }
            })
        
        # 6. Product Reception (if received)
        if product.received_at and product.received_by_shop:
            timeline.append({
                'stage': 'Product Reception',
                'category': 'shop',
                'timestamp': product.received_at.isoformat(),
                'location': product.received_by_shop.name,
                'action': 'Product received at shop',
                'icon': 'fa-store',
                'details': {
                    'Shop': product.received_by_shop.name,
                    'Quantity Received': f"{product.quantity_received} {self.weight_unit}",
                    'Status': 'Accepted'
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


class RejectionReason(models.Model):
    """Model for storing rejection reasons for animals and parts during receive process"""

    REJECTION_CATEGORY_CHOICES = [
        ('quality', 'Quality Issues'),
        ('documentation', 'Documentation Issues'),
        ('health_safety', 'Health & Safety'),
        ('compliance', 'Compliance Issues'),
        ('logistics', 'Logistics Issues'),
        ('other', 'Other'),
    ]

    SPECIFIC_REASON_CHOICES = [
        # Quality Issues
        ('poor_condition', 'Poor Physical Condition'),
        ('contamination', 'Contamination'),
        ('incorrect_weight', 'Incorrect Weight'),
        ('damage', 'Physical Damage'),
        ('expired', 'Expired/Outdated'),

        # Documentation Issues
        ('missing_docs', 'Missing Documentation'),
        ('invalid_docs', 'Invalid Documentation'),
        ('incomplete_records', 'Incomplete Records'),
        ('wrong_animal', 'Wrong Animal ID'),

        # Health & Safety
        ('disease_symptoms', 'Disease Symptoms'),
        ('parasites', 'Parasites/Insects'),
        ('chemical_residues', 'Chemical Residues'),
        ('temperature_issues', 'Temperature Issues'),

        # Compliance Issues
        ('certification_missing', 'Missing Certification'),
        ('traceability_breach', 'Traceability Breach'),
        ('regulatory_violation', 'Regulatory Violation'),

        # Logistics Issues
        ('transport_damage', 'Transport Damage'),
        ('delayed_delivery', 'Delayed Delivery'),
        ('packaging_issues', 'Packaging Issues'),

        # Other
        ('other', 'Other (Specify in Notes)'),
    ]

    # What was rejected
    animal = models.ForeignKey(Animal, on_delete=models.CASCADE, null=True, blank=True, related_name='rejection_reasons')
    slaughter_part = models.ForeignKey(SlaughterPart, on_delete=models.CASCADE, null=True, blank=True, related_name='rejection_reasons')

    # Rejection details
    category = models.CharField(max_length=20, choices=REJECTION_CATEGORY_CHOICES)
    specific_reason = models.CharField(max_length=30, choices=SPECIFIC_REASON_CHOICES)
    notes = models.TextField(blank=True, null=True, help_text="Additional notes about the rejection")

    # Processing details
    rejected_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='rejections_made')
    processing_unit = models.ForeignKey(ProcessingUnit, on_delete=models.SET_NULL, null=True, related_name='rejections')
    rejected_at = models.DateTimeField(default=timezone.now)

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-rejected_at']
        indexes = [
            models.Index(fields=['animal', 'rejected_at']),
            models.Index(fields=['slaughter_part', 'rejected_at']),
            models.Index(fields=['category', 'rejected_at']),
            models.Index(fields=['processing_unit', 'rejected_at']),
        ]

    def __str__(self):
        target = self.animal.animal_id if self.animal else f"Part {self.slaughter_part.part_id}"
        return f"Rejection of {target}: {self.get_category_display()} - {self.get_specific_reason_display()}"

    def clean(self):
        """Validate that either animal or slaughter_part is set, but not both"""
        from django.core.exceptions import ValidationError

        if not self.animal and not self.slaughter_part:
            raise ValidationError("Either animal or slaughter_part must be specified")

        if self.animal and self.slaughter_part:
            raise ValidationError("Cannot specify both animal and slaughter_part - choose one")


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


# ══════════════════════════════════════════════════════════════════════════════
# COMPLIANCE AND AUDIT MODELS
# ══════════════════════════════════════════════════════════════════════════════

class ComplianceStatus(models.Model):
    """Model for tracking compliance status of entities (processing units, shops, products)"""

    ENTITY_TYPE_CHOICES = [
        ('processing_unit', 'Processing Unit'),
        ('shop', 'Shop'),
        ('product', 'Product'),
        ('animal', 'Animal'),
        ('user', 'User'),
    ]

    COMPLIANCE_LEVEL_CHOICES = [
        ('compliant', 'Compliant'),
        ('warning', 'Warning'),
        ('non_compliant', 'Non-Compliant'),
        ('critical', 'Critical Violation'),
    ]

    # Entity being tracked
    entity_type = models.CharField(max_length=20, choices=ENTITY_TYPE_CHOICES)
    entity_id = models.PositiveIntegerField(help_text="ID of the entity being tracked")

    # Compliance details
    compliance_level = models.CharField(max_length=20, choices=COMPLIANCE_LEVEL_CHOICES, default='compliant')
    compliance_score = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)], help_text="Compliance score (0-100)")

    # Issues and violations
    issues_count = models.PositiveIntegerField(default=0, help_text="Number of compliance issues")
    critical_issues_count = models.PositiveIntegerField(default=0, help_text="Number of critical compliance issues")
    last_violation_date = models.DateTimeField(null=True, blank=True, help_text="Date of last compliance violation")

    # Compliance requirements
    required_certifications = models.JSONField(default=list, help_text="List of required certifications")
    obtained_certifications = models.JSONField(default=list, help_text="List of obtained certifications")
    certification_expiry_dates = models.JSONField(default=dict, help_text="Certification expiry dates")

    # Traceability compliance
    traceability_score = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)], default=100, help_text="Traceability compliance score")
    documentation_completeness = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)], default=100, help_text="Documentation completeness score")

    # Quality compliance
    quality_score = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)], default=100, help_text="Quality compliance score")
    safety_score = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)], default=100, help_text="Safety compliance score")

    # Metadata
    last_audit_date = models.DateTimeField(null=True, blank=True, help_text="Date of last compliance audit")
    next_audit_due = models.DateTimeField(null=True, blank=True, help_text="Date when next audit is due")
    audit_frequency_days = models.PositiveIntegerField(default=90, help_text="Audit frequency in days")

    # Status tracking
    is_active = models.BooleanField(default=True, help_text="Whether this compliance record is active")
    status_updated_at = models.DateTimeField(auto_now=True)
    status_updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='compliance_status_updates')

    # Additional data
    compliance_notes = models.TextField(blank=True, null=True, help_text="Additional compliance notes")
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional compliance metadata")

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['entity_type', 'entity_id']
        indexes = [
            models.Index(fields=['entity_type', 'compliance_level']),
            models.Index(fields=['compliance_level', 'last_violation_date']),
            models.Index(fields=['next_audit_due', 'is_active']),
            models.Index(fields=['compliance_score']),
            models.Index(fields=['traceability_score']),
            models.Index(fields=['quality_score']),
            models.Index(fields=['safety_score']),
        ]

    def __str__(self):
        return f"{self.entity_type} {self.entity_id} - {self.compliance_level} ({self.compliance_score}%)"

    def calculate_overall_score(self):
        """Calculate overall compliance score based on component scores"""
        weights = {
            'traceability': 0.4,
            'documentation': 0.3,
            'quality': 0.15,
            'safety': 0.15
        }

        overall_score = (
            self.traceability_score * weights['traceability'] +
            self.documentation_completeness * weights['documentation'] +
            self.quality_score * weights['quality'] +
            self.safety_score * weights['safety']
        )

        self.compliance_score = round(overall_score, 2)

        # Update compliance level based on score
        if self.compliance_score >= 90:
            self.compliance_level = 'compliant'
        elif self.compliance_score >= 70:
            self.compliance_level = 'warning'
        elif self.compliance_score >= 50:
            self.compliance_level = 'non_compliant'
        else:
            self.compliance_level = 'critical'

        return self.compliance_score

    def update_certification_status(self):
        """Update certification compliance based on expiry dates"""
        from datetime import timedelta
        now = timezone.now()
        warning_period = timedelta(days=30)  # Warn 30 days before expiry

        expired_certs = []
        expiring_soon_certs = []

        for cert_name, expiry_date_str in self.certification_expiry_dates.items():
            try:
                expiry_date = timezone.datetime.fromisoformat(expiry_date_str.replace('Z', '+00:00'))
                if expiry_date < now:
                    expired_certs.append(cert_name)
                elif expiry_date < now + warning_period:
                    expiring_soon_certs.append(cert_name)
            except (ValueError, TypeError):
                continue

        # Update metadata with certification status
        self.metadata['expired_certifications'] = expired_certs
        self.metadata['expiring_soon_certifications'] = expiring_soon_certs

        # Adjust compliance score for expired certifications
        if expired_certs:
            penalty = min(len(expired_certs) * 20, 50)  # Max 50 point penalty
            self.compliance_score = max(0, self.compliance_score - penalty)
            if self.compliance_score < 50:
                self.compliance_level = 'critical'


class AuditTrail(models.Model):
    """Partitioned model for comprehensive audit trail logging"""

    ACTION_TYPE_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('view', 'View'),
        ('export', 'Export'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('transfer', 'Transfer'),
        ('reject', 'Reject'),
        ('approve', 'Approve'),
        ('audit', 'Audit'),
        ('compliance_check', 'Compliance Check'),
        ('system', 'System Action'),
    ]

    ENTITY_TYPE_CHOICES = [
        ('user', 'User'),
        ('animal', 'Animal'),
        ('slaughter_part', 'Slaughter Part'),
        ('product', 'Product'),
        ('processing_unit', 'Processing Unit'),
        ('shop', 'Shop'),
        ('order', 'Order'),
        ('sale', 'Sale'),
        ('inventory', 'Inventory'),
        ('system', 'System'),
    ]

    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    # Partitioning field - must be part of primary key for partitioning
    event_date = models.DateField(help_text="Date of the audit event (used for partitioning)")

    # Audit event details
    timestamp = models.DateTimeField(default=timezone.now, help_text="Exact timestamp of the event")
    action_type = models.CharField(max_length=20, choices=ACTION_TYPE_CHOICES)
    entity_type = models.CharField(max_length=20, choices=ENTITY_TYPE_CHOICES)
    entity_id = models.PositiveIntegerField(null=True, blank=True, help_text="ID of the entity being audited")

    # User information
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_trail_entries')
    user_role = models.CharField(max_length=20, blank=True, null=True, help_text="Role of the user at time of action")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)

    # Action details
    action_description = models.TextField(help_text="Description of the action performed")
    old_values = models.JSONField(default=dict, blank=True, help_text="Previous values before the change")
    new_values = models.JSONField(default=dict, blank=True, help_text="New values after the change")

    # Compliance and security
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='low')
    compliance_related = models.BooleanField(default=False, help_text="Whether this action is compliance-related")
    security_event = models.BooleanField(default=False, help_text="Whether this is a security-related event")

    # Context information
    processing_unit = models.ForeignKey(ProcessingUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_trail')
    shop = models.ForeignKey(Shop, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_trail')

    # Additional metadata
    session_id = models.CharField(max_length=100, blank=True, null=True, help_text="User session identifier")
    request_id = models.CharField(max_length=100, blank=True, null=True, help_text="Request identifier for tracing")
    api_endpoint = models.CharField(max_length=200, blank=True, null=True, help_text="API endpoint accessed")
    http_method = models.CharField(max_length=10, blank=True, null=True, help_text="HTTP method used")

    # Audit metadata
    audit_batch_id = models.CharField(max_length=100, blank=True, null=True, help_text="Batch ID for grouped audit operations")
    retention_class = models.CharField(max_length=20, default='standard', help_text="Data retention classification")

    # Additional data
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional audit metadata")
    tags = models.JSONField(default=list, blank=True, help_text="Tags for categorization and filtering")

    class Meta:
        ordering = ['-timestamp']
        # Partitioning by event_date for efficient querying and retention
        # Note: Actual partitioning is configured in migration files
        indexes = [
            models.Index(fields=['event_date', 'timestamp']),
            models.Index(fields=['entity_type', 'entity_id', 'event_date']),
            models.Index(fields=['user', 'event_date']),
            models.Index(fields=['action_type', 'event_date']),
            models.Index(fields=['severity', 'event_date']),
            models.Index(fields=['compliance_related', 'event_date']),
            models.Index(fields=['security_event', 'event_date']),
            models.Index(fields=['processing_unit', 'event_date']),
            models.Index(fields=['shop', 'event_date']),
            models.Index(fields=['retention_class', 'event_date']),
            models.Index(fields=['audit_batch_id']),
            models.Index(fields=['session_id']),
            models.Index(fields=['request_id']),
        ]

    def __str__(self):
        user_info = self.user.username if self.user else 'System'
        return f"{self.action_type} on {self.entity_type} {self.entity_id or ''} by {user_info} at {self.timestamp}"

    def save(self, *args, **kwargs):
        # Ensure event_date is set from timestamp
        if not self.event_date:
            self.event_date = self.timestamp.date()

        # Set user role if user is provided
        if self.user and not self.user_role:
            try:
                self.user_role = self.user.profile.role
            except:
                self.user_role = 'Unknown'

        super().save(*args, **kwargs)

    @property
    def changes_summary(self):
        """Generate a summary of changes made"""
        if not self.old_values and not self.new_values:
            return "No changes recorded"

        changes = []
        all_keys = set(self.old_values.keys()) | set(self.new_values.keys())

        for key in all_keys:
            old_val = self.old_values.get(key, 'Not set')
            new_val = self.new_values.get(key, 'Not set')
            if old_val != new_val:
                changes.append(f"{key}: {old_val} → {new_val}")

        return "; ".join(changes) if changes else "No changes detected"


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION MANAGEMENT MODELS
# ══════════════════════════════════════════════════════════════════════════════

class SystemConfiguration(models.Model):
    """Model for system-wide configuration settings with versioning and validation"""

    DATA_TYPE_CHOICES = [
        ('string', 'String'),
        ('integer', 'Integer'),
        ('float', 'Float'),
        ('boolean', 'Boolean'),
        ('json', 'JSON'),
    ]

    CATEGORY_CHOICES = [
        ('general', 'General'),
        ('database', 'Database'),
        ('cache', 'Cache'),
        ('logging', 'Logging'),
        ('monitoring', 'Monitoring'),
        ('security', 'Security'),
        ('api', 'API'),
        ('notification', 'Notification'),
    ]

    ENVIRONMENT_CHOICES = [
        ('development', 'Development'),
        ('staging', 'Staging'),
        ('production', 'Production'),
    ]

    # Configuration key
    key = models.CharField(max_length=255, unique=True, help_text="Configuration key (e.g., 'database.connection_pool.max_size')")

    # Current value
    value = models.TextField(help_text="Current configuration value")
    default_value = models.TextField(blank=True, null=True, help_text="Default value if not set")

    # Metadata
    data_type = models.CharField(max_length=20, choices=DATA_TYPE_CHOICES, default='string')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')
    environment = models.CharField(max_length=20, choices=ENVIRONMENT_CHOICES, default='production')

    # Validation and constraints
    validation_rules = models.JSONField(default=dict, blank=True, help_text="JSON validation rules (min, max, required, etc.)")
    is_sensitive = models.BooleanField(default=False, help_text="Whether this config contains sensitive data")
    requires_restart = models.BooleanField(default=False, help_text="Whether changing this config requires system restart")

    # Description and tags
    description = models.TextField(blank=True, null=True)
    tags = models.JSONField(default=list, blank=True, help_text="List of tags for organization")

    # Versioning
    version = models.PositiveIntegerField(default=1, help_text="Current version number")

    # Audit fields
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_configs')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_configs')

    class Meta:
        ordering = ['category', 'key']
        indexes = [
            models.Index(fields=['category', 'environment']),
            models.Index(fields=['key']),
            models.Index(fields=['is_sensitive']),
            models.Index(fields=['requires_restart']),
        ]

    def __str__(self):
        return f"{self.key} ({self.environment})"

    def save(self, *args, **kwargs):
        # Increment version on update
        if self.pk:
            self.version += 1
        super().save(*args, **kwargs)

    def get_typed_value(self):
        """Return the value cast to the appropriate data type"""
        if self.data_type == 'integer':
            return int(self.value)
        elif self.data_type == 'float':
            return float(self.value)
        elif self.data_type == 'boolean':
            return self.value.lower() in ('true', '1', 'yes', 'on')
        elif self.data_type == 'json':
            return json.loads(self.value)
        return self.value

    def validate_value(self, value):
        """Validate a value against the configuration rules"""
        rules = self.validation_rules or {}

        if rules.get('required', False) and not value:
            raise ValueError("Value is required")

        if self.data_type == 'integer':
            try:
                int_val = int(value)
                if 'min' in rules and int_val < rules['min']:
                    raise ValueError(f"Value must be >= {rules['min']}")
                if 'max' in rules and int_val > rules['max']:
                    raise ValueError(f"Value must be <= {rules['max']}")
            except ValueError:
                raise ValueError("Value must be a valid integer")

        elif self.data_type == 'float':
            try:
                float_val = float(value)
                if 'min' in rules and float_val < rules['min']:
                    raise ValueError(f"Value must be >= {rules['min']}")
                if 'max' in rules and float_val > rules['max']:
                    raise ValueError(f"Value must be <= {rules['max']}")
            except ValueError:
                raise ValueError("Value must be a valid number")

        return True


class ConfigurationHistory(models.Model):
    """Model for tracking configuration changes over time"""

    ACTION_CHOICES = [
        ('created', 'Created'),
        ('updated', 'Updated'),
        ('deleted', 'Deleted'),
        ('rollback', 'Rolled Back'),
    ]

    # Related configuration
    configuration = models.ForeignKey(SystemConfiguration, on_delete=models.CASCADE, related_name='history')

    # Change details
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)

    # Version info
    version = models.PositiveIntegerField(help_text="Version number at time of change")

    # Change metadata
    reason = models.TextField(blank=True, null=True, help_text="Reason for the change")
    validation_status = models.CharField(max_length=20, default='passed', help_text="Validation status of the change")
    rollback_available = models.BooleanField(default=True, help_text="Whether this change can be rolled back to")

    # Audit
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='config_changes')
    changed_at = models.DateTimeField(default=timezone.now)

    # Additional metadata
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-changed_at']
        indexes = [
            models.Index(fields=['configuration', 'changed_at']),
            models.Index(fields=['action', 'changed_at']),
            models.Index(fields=['changed_by', 'changed_at']),
        ]

    def __str__(self):
        return f"{self.configuration.key} v{self.version} - {self.action}"


class FeatureFlag(models.Model):
    """Model for feature flags with rollout control and targeting"""

    STATUS_CHOICES = [
        ('enabled', 'Enabled'),
        ('disabled', 'Disabled'),
        ('scheduled', 'Scheduled'),
    ]

    TARGET_TYPE_CHOICES = [
        ('all_users', 'All Users'),
        ('percentage', 'Percentage Rollout'),
        ('user_list', 'Specific Users'),
        ('user_segments', 'User Segments'),
    ]

    # Basic flag info
    name = models.CharField(max_length=100, unique=True)
    key = models.CharField(max_length=100, unique=True, help_text="Unique identifier for the feature flag")
    description = models.TextField(blank=True, null=True)

    # Status and environment
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='disabled')
    environment = models.CharField(max_length=20, choices=SystemConfiguration.ENVIRONMENT_CHOICES, default='production')

    # Targeting rules
    target_audience = models.JSONField(default=dict, help_text="""
    Targeting rules: {
        "type": "percentage|user_list|user_segments|all_users",
        "percentage": 50,  # for percentage type
        "user_ids": [1,2,3],  # for user_list type
        "user_segments": ["admins", "farmers"],  # for user_segments type
        "excluded_users": [4,5]  # users to exclude
    }
    """)

    # Rollout scheduling
    rollout_schedule = models.JSONField(default=dict, blank=True, help_text="""
    Rollout schedule: {
        "start_date": "2025-11-01T00:00:00Z",
        "end_date": null,
        "gradual_rollout": true,
        "rollout_percentage_per_day": 10
    }
    """)

    # Safety features
    kill_switch_enabled = models.BooleanField(default=True, help_text="Whether this flag can be quickly disabled")
    monitoring_enabled = models.BooleanField(default=True, help_text="Whether usage is being monitored")

    # Dependencies and relationships
    dependencies = models.JSONField(default=list, blank=True, help_text="List of feature flag keys this depends on")
    tags = models.JSONField(default=list, blank=True, help_text="Tags for organization")

    # Versioning
    version = models.PositiveIntegerField(default=1)

    # Audit
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_flags')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_flags')

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['key']),
            models.Index(fields=['status', 'environment']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.name} ({self.status})"

    def is_enabled_for_user(self, user):
        """Check if this feature flag is enabled for a specific user"""
        if self.status != 'enabled':
            return False

        audience = self.target_audience or {}

        # Check if user is excluded
        excluded_users = audience.get('excluded_users', [])
        if user.id in excluded_users:
            return False

        target_type = audience.get('type', 'all_users')

        if target_type == 'all_users':
            return True
        elif target_type == 'percentage':
            percentage = audience.get('percentage', 0)
            # Simple percentage-based rollout using user ID hash
            return (user.id % 100) < percentage
        elif target_type == 'user_list':
            user_ids = audience.get('user_ids', [])
            return user.id in user_ids
        elif target_type == 'user_segments':
            # This would need to be implemented based on user roles/segments
            # For now, return False as placeholder
            return False

        return False

    def get_rollout_progress(self):
        """Get current rollout progress information"""
        schedule = self.rollout_schedule or {}
        if not schedule.get('gradual_rollout', False):
            return {'progress': 100 if self.status == 'enabled' else 0}

        # Calculate progress based on schedule
        start_date = schedule.get('start_date')
        end_date = schedule.get('end_date')
        percentage_per_day = schedule.get('rollout_percentage_per_day', 0)

        if not start_date:
            return {'progress': 0}

        # This is a simplified calculation - in production you'd want more sophisticated logic
        return {'progress': 50}  # Placeholder


# ══════════════════════════════════════════════════════════════════════════════
# DATA MANAGEMENT MODELS
# ══════════════════════════════════════════════════════════════════════════════

class Backup(models.Model):
    """Model for tracking system backups with scheduling and status"""

    BACKUP_TYPE_CHOICES = [
        ('full', 'Full Backup'),
        ('incremental', 'Incremental Backup'),
        ('differential', 'Differential Backup'),
    ]

    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    # Backup identification
    name = models.CharField(max_length=200, help_text="Descriptive name for the backup")
    backup_id = models.CharField(max_length=50, unique=True, editable=False, help_text="Auto-generated unique backup identifier")

    # Backup configuration
    backup_type = models.CharField(max_length=20, choices=BACKUP_TYPE_CHOICES, default='full')
    include_database = models.BooleanField(default=True, help_text="Include database in backup")
    include_files = models.BooleanField(default=True, help_text="Include uploaded files in backup")
    include_media = models.BooleanField(default=True, help_text="Include media files in backup")

    # Backup scope and filters
    tables_to_include = models.JSONField(default=list, blank=True, help_text="Specific tables to include (empty means all)")
    tables_to_exclude = models.JSONField(default=list, blank=True, help_text="Tables to exclude from backup")

    # Status and progress
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    progress_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    file_path = models.CharField(max_length=500, blank=True, null=True, help_text="Path to backup file")
    file_size_bytes = models.BigIntegerField(null=True, blank=True, help_text="Size of backup file in bytes")

    # Timing
    scheduled_at = models.DateTimeField(null=True, blank=True, help_text="When the backup was scheduled")
    started_at = models.DateTimeField(null=True, blank=True, help_text="When the backup started")
    completed_at = models.DateTimeField(null=True, blank=True, help_text="When the backup completed")

    # Error handling
    error_message = models.TextField(blank=True, null=True, help_text="Error message if backup failed")
    retry_count = models.PositiveIntegerField(default=0, help_text="Number of retry attempts")

    # Retention and cleanup
    retention_days = models.PositiveIntegerField(default=30, help_text="How long to keep this backup")
    is_archived = models.BooleanField(default=False, help_text="Whether backup has been archived")
    archived_at = models.DateTimeField(null=True, blank=True, help_text="When backup was archived")

    # Audit
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_backups')
    initiated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='initiated_backups')

    # Metadata
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional backup metadata")
    checksum = models.CharField(max_length=128, blank=True, null=True, help_text="Checksum for backup integrity verification")

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['backup_type', 'status']),
            models.Index(fields=['scheduled_at', 'status']),
            models.Index(fields=['is_archived', 'retention_days']),
            models.Index(fields=['backup_id']),
        ]

    def __str__(self):
        return f"{self.name} ({self.backup_type} - {self.status})"

    def save(self, *args, **kwargs):
        # Generate backup_id if not set
        if not self.backup_id:
            self.backup_id = self._generate_backup_id()
        super().save(*args, **kwargs)

    def _generate_backup_id(self):
        """Generate a unique backup ID"""
        return f"BKP_{uuid.uuid4().hex[:12].upper()}"

    @property
    def duration(self):
        """Calculate backup duration"""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None

    @property
    def is_expired(self):
        """Check if backup has expired based on retention policy"""
        if not self.retention_days:
            return False
        expiry_date = self.created_at + timezone.timedelta(days=self.retention_days)
        return timezone.now() > expiry_date

    @property
    def file_size_mb(self):
        """Get file size in MB"""
        if self.file_size_bytes:
            return round(self.file_size_bytes / (1024 * 1024), 2)
        return None


class DataExport(models.Model):
    """Model for tracking data export operations"""

    EXPORT_FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('json', 'JSON'),
        ('xml', 'XML'),
        ('excel', 'Excel'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    # Export identification
    name = models.CharField(max_length=200, help_text="Descriptive name for the export")
    export_id = models.CharField(max_length=50, unique=True, editable=False, help_text="Auto-generated unique export identifier")

    # Export configuration
    export_format = models.CharField(max_length=10, choices=EXPORT_FORMAT_CHOICES, default='csv')
    include_related_data = models.BooleanField(default=True, help_text="Include related/foreign key data")

    # Data scope
    models_to_export = models.JSONField(default=list, blank=True, help_text="Specific models to export (empty means all)")
    filters = models.JSONField(default=dict, blank=True, help_text="Filters to apply to exported data")
    date_range_start = models.DateTimeField(null=True, blank=True, help_text="Start date for data filtering")
    date_range_end = models.DateTimeField(null=True, blank=True, help_text="End date for data filtering")

    # Status and progress
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    progress_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    records_exported = models.PositiveIntegerField(default=0, help_text="Number of records exported")
    file_path = models.CharField(max_length=500, blank=True, null=True, help_text="Path to exported file")
    file_size_bytes = models.BigIntegerField(null=True, blank=True, help_text="Size of exported file in bytes")

    # Timing
    scheduled_at = models.DateTimeField(null=True, blank=True, help_text="When the export was scheduled")
    started_at = models.DateTimeField(null=True, blank=True, help_text="When the export started")
    completed_at = models.DateTimeField(null=True, blank=True, help_text="When the export completed")

    # Error handling
    error_message = models.TextField(blank=True, null=True, help_text="Error message if export failed")

    # Audit
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_exports')
    initiated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='initiated_exports')

    # Metadata
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional export metadata")

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['export_format', 'status']),
            models.Index(fields=['scheduled_at', 'status']),
            models.Index(fields=['export_id']),
        ]

    def __str__(self):
        return f"{self.name} ({self.export_format} - {self.status})"

    def save(self, *args, **kwargs):
        # Generate export_id if not set
        if not self.export_id:
            self.export_id = self._generate_export_id()
        super().save(*args, **kwargs)

    def _generate_export_id(self):
        """Generate a unique export ID"""
        return f"EXP_{uuid.uuid4().hex[:12].upper()}"


class DataImport(models.Model):
    """Model for tracking data import operations"""

    IMPORT_FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('json', 'JSON'),
        ('xml', 'XML'),
        ('excel', 'Excel'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('validating', 'Validating'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    # Import identification
    name = models.CharField(max_length=200, help_text="Descriptive name for the import")
    import_id = models.CharField(max_length=50, unique=True, editable=False, help_text="Auto-generated unique import identifier")

    # Import configuration
    import_format = models.CharField(max_length=10, choices=IMPORT_FORMAT_CHOICES, default='csv')
    source_file_path = models.CharField(max_length=500, help_text="Path to source file for import")
    target_model = models.CharField(max_length=100, help_text="Django model to import data into")

    # Import options
    update_existing = models.BooleanField(default=False, help_text="Update existing records if they match")
    skip_duplicates = models.BooleanField(default=True, help_text="Skip duplicate records")
    validate_data = models.BooleanField(default=True, help_text="Validate data before import")

    # Status and progress
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    progress_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    records_processed = models.PositiveIntegerField(default=0, help_text="Number of records processed")
    records_imported = models.PositiveIntegerField(default=0, help_text="Number of records successfully imported")
    records_failed = models.PositiveIntegerField(default=0, help_text="Number of records that failed to import")

    # Validation results
    validation_errors = models.JSONField(default=list, blank=True, help_text="List of validation errors")
    duplicate_records = models.JSONField(default=list, blank=True, help_text="List of duplicate records found")

    # Timing
    scheduled_at = models.DateTimeField(null=True, blank=True, help_text="When the import was scheduled")
    started_at = models.DateTimeField(null=True, blank=True, help_text="When the import started")
    completed_at = models.DateTimeField(null=True, blank=True, help_text="When the import completed")

    # Error handling
    error_message = models.TextField(blank=True, null=True, help_text="Error message if import failed")

    # Audit
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_imports')
    initiated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='initiated_imports')

    # Metadata
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional import metadata")

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['import_format', 'status']),
            models.Index(fields=['target_model', 'status']),
            models.Index(fields=['scheduled_at', 'status']),
            models.Index(fields=['import_id']),
        ]

    def __str__(self):
        return f"{self.name} ({self.import_format} - {self.status})"

    def save(self, *args, **kwargs):
        # Generate import_id if not set
        if not self.import_id:
            self.import_id = self._generate_import_id()
        super().save(*args, **kwargs)

    def _generate_import_id(self):
        """Generate a unique import ID"""
        return f"IMP_{uuid.uuid4().hex[:12].upper()}"


class GDPRRequest(models.Model):
    """Model for tracking GDPR compliance requests (data deletion, anonymization)"""

    REQUEST_TYPE_CHOICES = [
        ('data_deletion', 'Data Deletion'),
        ('data_anonymization', 'Data Anonymization'),
        ('data_portability', 'Data Portability'),
        ('access_request', 'Access Request'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]

    # Request identification
    request_id = models.CharField(max_length=50, unique=True, editable=False, help_text="Auto-generated unique request identifier")

    # Request details
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPE_CHOICES)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='gdpr_requests', help_text="User making the request")
    justification = models.TextField(blank=True, null=True, help_text="User's justification for the request")

    # Data scope
    data_categories = models.JSONField(default=list, blank=True, help_text="Categories of data to process")
    date_range_start = models.DateTimeField(null=True, blank=True, help_text="Start date for data processing")
    date_range_end = models.DateTimeField(null=True, blank=True, help_text="End date for data processing")

    # Status and progress
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    progress_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])

    # Processing details
    processed_data_summary = models.JSONField(default=dict, blank=True, help_text="Summary of data processed")
    anonymized_fields = models.JSONField(default=list, blank=True, help_text="Fields that were anonymized")
    deleted_records = models.JSONField(default=list, blank=True, help_text="Records that were deleted")

    # Response
    admin_notes = models.TextField(blank=True, null=True, help_text="Admin notes on processing")
    response_message = models.TextField(blank=True, null=True, help_text="Response message to user")

    # Timing
    requested_at = models.DateTimeField(default=timezone.now, help_text="When the request was made")
    processed_at = models.DateTimeField(null=True, blank=True, help_text="When the request was processed")
    completed_at = models.DateTimeField(null=True, blank=True, help_text="When the request was completed")

    # Audit
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_gdpr_requests')

    # Metadata
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional GDPR request metadata")

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['status', 'requested_at']),
            models.Index(fields=['request_type', 'status']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['request_id']),
        ]

    def __str__(self):
        return f"GDPR {self.request_type} for {self.user.username} ({self.status})"

    def save(self, *args, **kwargs):
        # Generate request_id if not set
        if not self.request_id:
            self.request_id = self._generate_request_id()
        super().save(*args, **kwargs)

    def _generate_request_id(self):
        """Generate a unique GDPR request ID"""
        return f"GDPR_{uuid.uuid4().hex[:12].upper()}"


class DataValidation(models.Model):
    """Model for tracking data validation and integrity checks"""

    VALIDATION_TYPE_CHOICES = [
        ('schema_validation', 'Schema Validation'),
        ('referential_integrity', 'Referential Integrity'),
        ('data_consistency', 'Data Consistency'),
        ('business_rules', 'Business Rules'),
        ('custom_validation', 'Custom Validation'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('passed', 'Passed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    # Validation identification
    name = models.CharField(max_length=200, help_text="Descriptive name for the validation")
    validation_id = models.CharField(max_length=50, unique=True, editable=False, help_text="Auto-generated unique validation identifier")

    # Validation configuration
    validation_type = models.CharField(max_length=25, choices=VALIDATION_TYPE_CHOICES)
    target_models = models.JSONField(default=list, blank=True, help_text="Models to validate")
    validation_rules = models.JSONField(default=dict, blank=True, help_text="Validation rules and parameters")

    # Status and results
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    progress_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])

    # Results
    records_checked = models.PositiveIntegerField(default=0, help_text="Number of records checked")
    records_passed = models.PositiveIntegerField(default=0, help_text="Number of records that passed validation")
    records_failed = models.PositiveIntegerField(default=0, help_text="Number of records that failed validation")

    # Error details
    validation_errors = models.JSONField(default=list, blank=True, help_text="List of validation errors found")
    error_summary = models.JSONField(default=dict, blank=True, help_text="Summary of validation errors")

    # Timing
    scheduled_at = models.DateTimeField(null=True, blank=True, help_text="When the validation was scheduled")
    started_at = models.DateTimeField(null=True, blank=True, help_text="When the validation started")
    completed_at = models.DateTimeField(null=True, blank=True, help_text="When the validation completed")

    # Error handling
    error_message = models.TextField(blank=True, null=True, help_text="Error message if validation failed")

    # Audit
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_validations')
    initiated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='initiated_validations')

    # Metadata
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional validation metadata")

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['validation_type', 'status']),
            models.Index(fields=['scheduled_at', 'status']),
            models.Index(fields=['validation_id']),
        ]

    def __str__(self):
        return f"{self.name} ({self.validation_type} - {self.status})"

    def save(self, *args, **kwargs):
        # Generate validation_id if not set
        if not self.validation_id:
            self.validation_id = self._generate_validation_id()
        super().save(*args, **kwargs)

    def _generate_validation_id(self):
        """Generate a unique validation ID"""
        return f"VAL_{uuid.uuid4().hex[:12].upper()}"


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
