#!/usr/bin/env python
import os
import sys
import django

# Add the project directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')

# Setup Django
django.setup()

# Now import and check views
try:
    from meat_trace.views import *
    print("All views imported successfully")

    # Check for specific viewsets and views
    all_items = [name for name in dir() if not name.startswith('_') and name != 'django' and name != 'os' and name != 'sys']
    viewsets = [name for name in all_items if 'ViewSet' in name or 'View' in name]
    functions = [name for name in all_items if not ('ViewSet' in name or 'View' in name) and callable(globals().get(name, None))]

    print(f"Found {len(viewsets)} viewsets/views:")
    for vs in sorted(viewsets):
        print(f"  - {vs}")

    print(f"Found {len(functions)} functions:")
    for fn in sorted(functions):
        print(f"  - {fn}")

except ImportError as e:
    print(f"Import error: {e}")
    import traceback
    traceback.print_exc()