"""
Custom throttling classes for MeatTrace API.
"""
from rest_framework.throttling import UserRateThrottle


class AdminRateThrottle(UserRateThrottle):
    """
    Rate throttle specifically for admin endpoints.
    Limits admin users to 100 requests per minute.
    """
    scope = 'admin'
    rate = '100/minute'
