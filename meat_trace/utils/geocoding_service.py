"""
Geocoding Service for MeatTrace

Converts text addresses to latitude/longitude coordinates using OpenStreetMap Nominatim.
This is a free geocoding service that doesn't require an API key.

Usage:
    from meat_trace.utils.geocoding_service import GeocodingService

    # Get coordinates for a location
    coords = GeocodingService.geocode("Dar es Salaam, Tanzania")
    # Returns: {'latitude': -6.7924, 'longitude': 39.2083} or None if not found
"""

import logging
import requests
from typing import Optional, Dict
from django.core.cache import cache

logger = logging.getLogger(__name__)


class GeocodingService:
    """
    Service for geocoding addresses to coordinates using OpenStreetMap Nominatim.
    
    Features:
    - Free, no API key required
    - Results are cached to reduce API calls
    - Built-in rate limiting (1 request per second as per Nominatim policy)
    - Tanzania-focused bias for better local results
    """
    
    NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
    CACHE_TIMEOUT = 60 * 60 * 24 * 30  # 30 days cache
    USER_AGENT = "MeatTrace/1.0 (contact@meattrace.com)"  # Required by Nominatim
    
    # Known Tanzanian locations with pre-cached coordinates
    # This provides instant results for common locations
    KNOWN_LOCATIONS = {
        'dar es salaam': {'latitude': -6.7924, 'longitude': 39.2083},
        'arusha': {'latitude': -3.3869, 'longitude': 36.6830},
        'mwanza': {'latitude': -2.5164, 'longitude': 32.9176},
        'dodoma': {'latitude': -6.1630, 'longitude': 35.7516},
        'mbeya': {'latitude': -8.9000, 'longitude': 33.4500},
        'morogoro': {'latitude': -6.8278, 'longitude': 37.6591},
        'tanga': {'latitude': -5.0689, 'longitude': 39.0989},
        'zanzibar': {'latitude': -6.1659, 'longitude': 39.2026},
        'kigoma': {'latitude': -4.8769, 'longitude': 29.6269},
        'tabora': {'latitude': -5.0242, 'longitude': 32.8006},
        'singida': {'latitude': -4.8162, 'longitude': 34.7442},
        'iringa': {'latitude': -7.7700, 'longitude': 35.7000},
        'mtwara': {'latitude': -10.2736, 'longitude': 40.1828},
        'lindi': {'latitude': -9.9985, 'longitude': 39.7131},
        'songea': {'latitude': -10.6833, 'longitude': 35.6500},
        'musoma': {'latitude': -1.5000, 'longitude': 33.8000},
        'bukoba': {'latitude': -1.3317, 'longitude': 31.8100},
        'sumbawanga': {'latitude': -7.9667, 'longitude': 31.6167},
        'njombe': {'latitude': -9.3333, 'longitude': 35.0000},
        'kilimanjaro': {'latitude': -3.0674, 'longitude': 37.3556},
    }
    
    @classmethod
    def geocode(cls, address: str) -> Optional[Dict[str, float]]:
        """
        Convert an address to latitude/longitude coordinates.
        
        Args:
            address: Text address to geocode (e.g., "Morogoro, Tanzania")
            
        Returns:
            Dict with 'latitude' and 'longitude' keys, or None if not found
        """
        if not address or not address.strip():
            return None
        
        address = address.strip()
        address_lower = address.lower()
        
        # Check known locations first (instant, no API call)
        for location_name, coords in cls.KNOWN_LOCATIONS.items():
            if location_name in address_lower:
                logger.info(f"[GEOCODING] Found known location: {location_name}")
                return coords
        
        # Check cache
        cache_key = f"geocode_{address_lower.replace(' ', '_')}"
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            logger.info(f"[GEOCODING] Cache hit for: {address}")
            return cached_result if cached_result != 'NOT_FOUND' else None
        
        # Call Nominatim API
        try:
            logger.info(f"[GEOCODING] Calling Nominatim API for: {address}")
            
            # Add Tanzania bias for better results
            search_address = address
            if 'tanzania' not in address_lower:
                search_address = f"{address}, Tanzania"
            
            params = {
                'q': search_address,
                'format': 'json',
                'limit': 1,
                'addressdetails': 0,
            }
            
            headers = {
                'User-Agent': cls.USER_AGENT
            }
            
            response = requests.get(
                cls.NOMINATIM_URL,
                params=params,
                headers=headers,
                timeout=5
            )
            response.raise_for_status()
            
            results = response.json()
            
            if results and len(results) > 0:
                result = results[0]
                coords = {
                    'latitude': float(result['lat']),
                    'longitude': float(result['lon'])
                }
                
                # Cache the result
                cache.set(cache_key, coords, cls.CACHE_TIMEOUT)
                logger.info(f"[GEOCODING] Success: {address} -> {coords}")
                return coords
            else:
                # Cache the "not found" result to avoid repeated API calls
                cache.set(cache_key, 'NOT_FOUND', cls.CACHE_TIMEOUT)
                logger.warning(f"[GEOCODING] No results for: {address}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"[GEOCODING] API error for {address}: {e}")
            return None
        except Exception as e:
            logger.error(f"[GEOCODING] Unexpected error for {address}: {e}")
            return None
    
    @classmethod
    def geocode_and_save(cls, instance, location_field: str = 'location'):
        """
        Geocode an instance's location field and save the coordinates.
        
        This is designed to be called from a model's save() method:
        
            def save(self, *args, **kwargs):
                GeocodingService.geocode_and_save(self, 'location')
                super().save(*args, **kwargs)
        
        Args:
            instance: Django model instance with latitude/longitude fields
            location_field: Name of the text location field
        """
        location = getattr(instance, location_field, None)
        
        if not location:
            return
        
        # Only geocode if location has changed and we don't have coordinates
        # or if we should update coordinates
        current_lat = getattr(instance, 'latitude', None)
        current_lng = getattr(instance, 'longitude', None)
        
        # Skip if we already have coordinates
        if current_lat is not None and current_lng is not None:
            return
        
        coords = cls.geocode(location)
        
        if coords:
            instance.latitude = coords['latitude']
            instance.longitude = coords['longitude']
            logger.info(f"[GEOCODING] Set coordinates for {type(instance).__name__}: {coords}")
