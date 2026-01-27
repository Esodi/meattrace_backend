"""
Role normalization utilities to handle inconsistent role naming across the codebase.

The system uses two role naming conventions:
- Model/Database: 'Abbatoir', 'Processor', 'ShopOwner', 'Admin' (capitalized)
- API/Frontend: 'abbatoir', 'processing_unit', 'shop', 'admin' (lowercase with underscores)

This utility ensures both conventions work seamlessly.
"""

# Canonical role constants (match UserProfile.ROLE_CHOICES)
ROLE_ABBATOIR = 'Abbatoir'
ROLE_PROCESSOR = 'Processor'
ROLE_SHOPOWNER = 'ShopOwner'
ROLE_ADMIN = 'Admin'

# Role normalization mapping (all variants map to canonical form)
ROLE_MAPPING = {
    # Abbatoir variants
    'abbatoir': ROLE_ABBATOIR,
    'Abbatoir': ROLE_ABBATOIR,
    'ABBATOIR': ROLE_ABBATOIR,
    
    # Processor variants
    'processor': ROLE_PROCESSOR,
    'Processor': ROLE_PROCESSOR,
    'PROCESSOR': ROLE_PROCESSOR,
    'processing_unit': ROLE_PROCESSOR,
    'ProcessingUnit': ROLE_PROCESSOR,
    'processing unit': ROLE_PROCESSOR,
    'processingunit': ROLE_PROCESSOR,
    
    # Shop Owner variants
    'shop': ROLE_SHOPOWNER,
    'Shop': ROLE_SHOPOWNER,
    'SHOP': ROLE_SHOPOWNER,
    'shopowner': ROLE_SHOPOWNER,
    'ShopOwner': ROLE_SHOPOWNER,
    'shop_owner': ROLE_SHOPOWNER,
    'shop owner': ROLE_SHOPOWNER,
    
    # Admin variants
    'admin': ROLE_ADMIN,
    'Admin': ROLE_ADMIN,
    'ADMIN': ROLE_ADMIN,
    'administrator': ROLE_ADMIN,
    'Administrator': ROLE_ADMIN,
}


def normalize_role(role):
    """
    Normalize a role string to its canonical form.
    
    Handles all naming conventions:
    - 'abbatoir' -> 'Abbatoir'
    - 'processing_unit' -> 'Processor'
    - 'Processor' -> 'Processor'
    - 'shop' -> 'ShopOwner'
    
    Args:
        role (str): Role string in any format
        
    Returns:
        str: Canonical role name or None if role is invalid
    """
    if not role:
        return None
    
    # First try exact match
    if role in ROLE_MAPPING:
        return ROLE_MAPPING[role]
    
    # Try case-insensitive with underscores/spaces removed
    normalized_key = role.lower().replace('_', '').replace(' ', '')
    
    for variant, canonical in ROLE_MAPPING.items():
        variant_normalized = variant.lower().replace('_', '').replace(' ', '')
        if normalized_key == variant_normalized:
            return canonical
    
    # If still not found, return the original (might be already canonical)
    return role


def is_abbatoir(user):
    """Check if user has abbatoir role"""
    if not hasattr(user, 'profile') or not user.profile:
        return False
    return normalize_role(user.profile.role) == ROLE_ABBATOIR


def is_processor(user):
    """Check if user has processor role"""
    if not hasattr(user, 'profile') or not user.profile:
        return False
    return normalize_role(user.profile.role) == ROLE_PROCESSOR


def is_shop_owner(user):
    """Check if user has shop owner role"""
    if not hasattr(user, 'profile') or not user.profile:
        return False
    return normalize_role(user.profile.role) == ROLE_SHOPOWNER


def is_admin(user):
    """Check if user has admin role"""
    if not hasattr(user, 'profile') or not user.profile:
        return False
    return normalize_role(user.profile.role) == ROLE_ADMIN


def get_user_role(user):
    """
    Get the canonical role for a user.
    
    Returns:
        str: Canonical role name or None
    """
    if not hasattr(user, 'profile') or not user.profile:
        return None
    return normalize_role(user.profile.role)
