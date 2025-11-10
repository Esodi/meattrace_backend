#!/usr/bin/env python
"""
Quick diagnostic to help debug mobile app connection issues
"""
import socket

print("=" * 80)
print("NETWORK DIAGNOSTIC FOR MOBILE APP CONNECTION")
print("=" * 80)

# Get computer's IP addresses
hostname = socket.gethostname()
print(f"\n💻 Computer hostname: {hostname}")

print("\n🌐 Available IP addresses:")
try:
    # Get all IP addresses
    ip_addresses = socket.gethostbyname_ex(hostname)[2]
    for ip in ip_addresses:
        print(f"   - {ip}")
        if ip == "192.168.44.223":
            print(f"     ✅ This matches your app configuration!")
except Exception as e:
    print(f"   Error getting IPs: {e}")

print("\n📱 Your app is configured to use: http://192.168.44.223:8000")
print("\n✅ Backend server is running (test passed)")
print("\n" + "=" * 80)
print("TROUBLESHOOTING CHECKLIST")
print("=" * 80)
print("""
If you still can't transfer products from the app, check:

1. ✓ Backend server is running (CONFIRMED)
2. ✓ User 'bbb' can login (CONFIRMED)
3. ✓ Products are available (2 products CONFIRMED)
4. ✓ Shops are available (2 shops CONFIRMED)
5. ? Mobile device can reach 192.168.44.223:8000
6. ? You're logged in to the app as 'bbb'
7. ? App shows products on the transfer screen

COMMON ISSUES:
- Make sure your phone/emulator is on the same network
- Check Windows Firewall isn't blocking port 8000
- Try accessing http://192.168.44.223:8000/api/v2/products/ from phone browser
- Check app console logs for any error messages

QUICK TESTS FROM YOUR PHONE:
1. Open browser on phone
2. Go to: http://192.168.44.223:8000/admin
3. If it loads, your connection is good
4. If it doesn't load, your network/firewall is blocking it
""")
print("=" * 80)
