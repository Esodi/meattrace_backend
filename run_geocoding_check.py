
import os
import django
import sys
import logging

# Setup Django environment
sys.path.append('/usr/apps/nyama_tamu/meattrace_backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from meat_trace.utils.geocoding_service import GeocodingService

# Configure logging to see output
logging.basicConfig(level=logging.INFO)

def test_geocoding():
    print("=== Testing Enhanced Geocoding Service ===\n")

    test_cases = [
        # 1. Known Region (should be instant)
        ("Region (Dar es Salaam)", "Dar es Salaam"),
        
        # 2. Known District (New functionality)
        ("District (Kinondoni)", "Kinondoni"),
        ("District (Ilala)", "Ilala"),
        ("District (Moshi - in Kilimanjaro)", "Kilimanjaro"), 
        
        # 3. Known Ward/Area
        ("Ward (Sinza)", "Sinza"),
        ("Ward (Kariakoo)", "Kariakoo"),
        ("Area (Mbezi Beach)", "Mbezi"),
        
        # 4. Unknown Specific Location (Should hit API with 'Tanzania' appended)
        # Note: These might fail if the API request fails or returns nothing, but the logic should try
        ("Village (Mbagala Kuu)", "Mbagala Kuu"),
        ("Street (Samora Avenue, Dar es Salaam)", "Samora Avenue, Dar es Salaam"),
    ]

    for label, address in test_cases:
        print(f"Testing {label} -> '{address}'")
        result = GeocodingService.geocode(address)
        if result:
            print(f"  SUCCESS: {result}")
        else:
            print(f"  FAILED: Could not geocode '{address}'")
        print("-" * 30)

    print("\n=== Testing Structured Geocoding ===")
    
    structured_cases = [
        {
            "label": "Street + City",
            "kwargs": {"street": "Samora Avenue", "city": "Dar es Salaam"}
        },
        {
            "label": "Ward + District",
            "kwargs": {"ward": "Sinza", "district": "Ubungo"}
        },
        {
            "label": "Village + Region",
            "kwargs": {"village": "Kijitonyama", "region": "Dar es Salaam"}
        }
    ]

    for case in structured_cases:
        print(f"Testing {case['label']}")
        result = GeocodingService.geocode_structured(**case['kwargs'])
        if result:
            print(f"  SUCCESS: {result}")
        else:
            print(f"  FAILED: Could not geocode structured query")
        print("-" * 30)

if __name__ == "__main__":
    test_geocoding()
