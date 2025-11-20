#!/usr/bin/env python3
"""
Development server runner for MeatTrace backend with WebSocket support.

This script starts an ASGI server that supports both HTTP and WebSocket connections,
making it suitable for development where you need real-time features like auth progress.

Usage:
    python runserver.py  # Starts on http://127.0.0.1:8000
    python runserver.py 0.0.0.0:8001  # Custom host/port
"""

import os
import sys
import subprocess
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_dependencies():
    """Check if required ASGI dependencies are installed."""
    try:
        import daphne
        print("✅ Daphne ASGI server found")
        return True
    except ImportError:
        print("❌ Daphne not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "daphne>=4.0"])
        print("✅ Daphne installed successfully")
        return True

def start_server(host="127.0.0.1", port=8000):
    """Start the ASGI development server with WebSocket support."""
    
    print("🚀 Starting MeatTrace Development Server")
    print("=" * 50)
    print(f"📡 WebSocket Support: ENABLED")
    print(f"🌐 Server URL: http://{host}:{port}")
    print(f"🔗 WebSocket URL: ws://{host}:{port}/ws/auth/progress/")
    print("=" * 50)
    
    # Set environment variables
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
    os.environ['PYTHONPATH'] = str(project_root)
    
    # Change to backend directory
    os.chdir(project_root)
    
    try:
        print("🔧 Starting Daphne ASGI server...")
        print("📝 Press Ctrl+C to stop the server")
        print("-" * 50)

        # Use subprocess to run daphne command
        cmd = [
            sys.executable, "-m", "daphne",
            "--bind", host,
            "--port", str(port),
            "--access-log", "-",
            "meattrace_backend.asgi:application"
        ]

        print(f"Running command: {' '.join(cmd)}")
        subprocess.run(cmd, cwd=project_root)
            
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        print("\n💡 Troubleshooting tips:")
        print("   1. Make sure all dependencies are installed: pip install -r requirements.txt")
        print("   2. Run database migrations: python manage.py migrate")
        print("   3. Check that Django Channels is installed: pip install channels")
        print("   4. Verify ASGI configuration in settings.py")

def main():
    """Main function to parse arguments and start the server."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="MeatTrace Development Server with WebSocket Support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python runserver.py                    # Start on default port 8000
  python runserver.py 0.0.0.0:8001      # Custom host and port
  python runserver.py 8080               # Custom port only
        """
    )
    
    parser.add_argument(
        'address',
        nargs='?',
        default='127.0.0.1:8000',
        help='Host and port to bind to (format: host:port or just port). Default: 127.0.0.1:8000'
    )
    
    args = parser.parse_args()
    
    # Parse host and port
    if ':' in args.address:
        host, port = args.address.split(':')
        port = int(port)
    else:
        host = '127.0.0.1'
        port = int(args.address)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Start server
    start_server(host=host, port=port)

if __name__ == '__main__':
    main()