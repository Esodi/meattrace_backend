#!/usr/bin/env python
import os
import sys
import django

# Add the project directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')

# Setup Django
django.setup()

# Now import and check serializers
try:
    from meat_trace.serializers import *
    print("All serializers imported successfully")

    # Check for specific serializers by trying to access them
    serializer_names = [
        'AnimalSerializer', 'ProductSerializer', 'ReceiptSerializer', 'ProductCategorySerializer',
        'ProcessingStageSerializer', 'ProductTimelineEventSerializer', 'InventorySerializer',
        'OrderSerializer', 'OrderItemSerializer', 'CarcassMeasurementSerializer', 'SlaughterPartSerializer',
        'ProcessingUnitSerializer', 'ProcessingUnitUserSerializer', 'ProductIngredientSerializer',
        'ShopSerializer', 'ShopUserSerializer', 'UserAuditLogSerializer'
    ]

    found_serializers = []
    for name in serializer_names:
        try:
            obj = globals()[name]
            found_serializers.append(f"{name}: {type(obj)}")
        except KeyError:
            pass

    print(f"Found {len(found_serializers)} serializer classes:")
    for ser in sorted(found_serializers):
        print(f"  - {ser}")

except ImportError as e:
    print(f"Import error: {e}")
    import traceback
    traceback.print_exc()