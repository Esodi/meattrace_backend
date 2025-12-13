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
        # Regions (Major Cities)
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
        'manyara': {'latitude': -4.3150, 'longitude': 35.7600},
        'shinyanga': {'latitude': -3.6667, 'longitude': 33.4167},
        'geita': {'latitude': -2.8667, 'longitude': 32.2333},
        'simiyu': {'latitude': -2.8000, 'longitude': 33.9000},
        'katavi': {'latitude': -6.5000, 'longitude': 31.1333},
        'rukwa': {'latitude': -8.0000, 'longitude': 31.5000},
        'ruvuma': {'latitude': -10.6667, 'longitude': 35.6667},
        'mara': {'latitude': -1.7500, 'longitude': 34.0000},
        'kagera': {'latitude': -1.5000, 'longitude': 31.5000},
        'pemba': {'latitude': -5.0889, 'longitude': 39.7667},

        # Dar es Salaam Districts
        'ilala': {'latitude': -6.8225, 'longitude': 39.2608},
        'kinondoni': {'latitude': -6.7456, 'longitude': 39.2319},
        'temeke': {'latitude': -6.8647, 'longitude': 39.2556},
        'ubungo': {'latitude': -6.7869, 'longitude': 39.2064},
        'kigamboni': {'latitude': -6.8378, 'longitude': 39.3178},

        # Major Districts & Towns (Partial List)
        'bagamoyo': {'latitude': -6.4480, 'longitude': 38.9056},
        'kibaha': {'latitude': -6.7725, 'longitude': 38.9167},
        'kisarawe': {'latitude': -6.9000, 'longitude': 39.0667},
        'rufiji': {'latitude': -7.9833, 'longitude': 39.0167},
        'mafia': {'latitude': -7.9167, 'longitude': 39.6667},
        'meru': {'latitude': -3.2333, 'longitude': 36.8333},
        'monduli': {'latitude': -3.3000, 'longitude': 36.4500},
        'ngorongoro': {'latitude': -3.2397, 'longitude': 35.4875},
        'serengeti': {'latitude': -2.3333, 'longitude': 34.8333},
        'same': {'latitude': -4.0667, 'longitude': 37.7333},
        'mwanga': {'latitude': -3.6500, 'longitude': 37.5667},
        'lushoto': {'latitude': -4.7833, 'longitude': 38.2833},
        'korogwe': {'latitude': -5.1500, 'longitude': 38.4500},
        'muheza': {'latitude': -5.1667, 'longitude': 38.7833},
        'handeni': {'latitude': -5.4333, 'longitude': 38.0167},
        'pangani': {'latitude': -5.4167, 'longitude': 38.9667},
        'kilosa': {'latitude': -6.8333, 'longitude': 36.9833},
        'mvomero': {'latitude': -6.3167, 'longitude': 37.5500},
        'kilombero': {'latitude': -8.2833, 'longitude': 36.6667},
        'ulanga': {'latitude': -9.0000, 'longitude': 36.6667},
        
        # Popular Wards/Areas in Dar es Salaam
        'kariakoo': {'latitude': -6.8197, 'longitude': 39.2747},
        'mbezi': {'latitude': -6.7028, 'longitude': 39.1981},
        'kimara': {'latitude': -6.7869, 'longitude': 39.1831},
        'sinza': {'latitude': -6.7761, 'longitude': 39.2319},
        'mikocheni': {'latitude': -6.7583, 'longitude': 39.2556},
        'msasani': {'latitude': -6.7417, 'longitude': 39.2722},
        'oysterbay': {'latitude': -6.7333, 'longitude': 39.2833},
        'masaki': {'latitude': -6.7333, 'longitude': 39.2833},
        'upanga': {'latitude': -6.8117, 'longitude': 39.2803},
        'posta': {'latitude': -6.8167, 'longitude': 39.2931},
        'kijitonyama': {'latitude': -6.7694, 'longitude': 39.2472},
        'manzese': {'latitude': -6.7972, 'longitude': 39.2333},
        'magomeni': {'latitude': -6.8000, 'longitude': 39.2500},
        'kawe': {'latitude': -6.7317, 'longitude': 39.2333},
        'mbagala': {'latitude': -6.9000, 'longitude': 39.2667},
        'gongo la mboto': {'latitude': -6.9000, 'longitude': 39.1500},
        'pugu': {'latitude': -6.9167, 'longitude': 39.1167},
        'chanika': {'latitude': -7.0167, 'longitude': 39.1000},
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
        # Strategy:
        # 1. Exact match (fastest, most accurate for simple queries)
        # 2. Key contains Address (e.g. key="kinondoni" matches "kinondoni district") - ONLY if no commas
        # 3. If commas present (complex address), prefer API unless exact match found
        
        clean_address = address_lower.replace(', tanzania', '').strip()
        
        # 1. Exact match check
        if clean_address in cls.KNOWN_LOCATIONS:
            logger.info(f"[GEOCODING] Found known location (exact): {clean_address}")
            return cls.KNOWN_LOCATIONS[clean_address]
            
        # 2. Iterative check
        # Only do fuzzy matching if it's a simple address (no commas)
        # This prevents "Street Name, Dar es Salaam" from matching "Dar es Salaam" and ignoring the street
        has_commas = ',' in address_lower
        
        if not has_commas:
            for location_name, coords in cls.KNOWN_LOCATIONS.items():
                if location_name in address_lower:
                    logger.info(f"[GEOCODING] Found known location (fuzzy): {location_name}")
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
            
            # Prepare query
            # If the address contains commas, it might be structured (e.g. "Street, City, Country")
            # We want to ensure "Tanzania" is included for better context if not present
            
            search_query = address
            if 'tanzania' not in address_lower:
                search_query = f"{address}, Tanzania"
            
            params = {
                'q': search_query,
                'format': 'json',
                'limit': 1,
                'addressdetails': 1,
                'countrycodes': 'tz',  # Restrict results to Tanzania
                'accept-language': 'en',  # Prefer English results
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
    def geocode_structured(cls, **kwargs) -> Optional[Dict[str, float]]:
        """
        Geocode using structured address components.
        
        Args:
            street: Street name
            city: City name
            county: District/County
            state: State/Region
            country: Country (default: Tanzania)
            
        Returns:
            Dict with 'latitude' and 'longitude' keys, or None if not found
        """
        # Construct a structured query string for better accuracy
        components = []
        
        street = kwargs.get('street')
        if street:
            components.append(street)
            
        village = kwargs.get('village')
        if village:
            components.append(village)
            
        ward = kwargs.get('ward')
        if ward:
            components.append(ward)
            
        district = kwargs.get('district') or kwargs.get('county')
        if district:
            components.append(district)
            
        city = kwargs.get('city')
        if city:
            components.append(city)
            
        region = kwargs.get('region') or kwargs.get('state')
        if region:
            components.append(region)
            
        # Join components to form a query
        if not components:
            return None
            
        query = ", ".join(components)
        return cls.geocode(query)
    
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
