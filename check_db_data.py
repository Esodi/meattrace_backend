import sqlite3
import os

# Connect to the database
db_path = 'db.sqlite3'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("=== DATABASE DATA CHECK ===")

    # Check users
    cursor.execute("SELECT COUNT(*) FROM auth_user")
    user_count = cursor.fetchone()[0]
    print(f"\nUsers: {user_count}")

    if user_count > 0:
        cursor.execute("SELECT id, username, email FROM auth_user LIMIT 5")
        users = cursor.fetchall()
        print("Sample users:")
        for user in users:
            print(f"  ID: {user[0]}, Username: {user[1]}, Email: {user[2]}")

    # Check user profiles
    cursor.execute("SELECT COUNT(*) FROM meat_trace_userprofile")
    profile_count = cursor.fetchone()[0]
    print(f"\nUser Profiles: {profile_count}")

    if profile_count > 0:
        cursor.execute("SELECT user_id, role, processing_unit_id, shop_id FROM meat_trace_userprofile LIMIT 5")
        profiles = cursor.fetchall()
        print("Sample profiles:")
        for profile in profiles:
            print(f"  User ID: {profile[0]}, Role: {profile[1]}, Processing Unit: {profile[2]}, Shop: {profile[3]}")

    # Check processing units
    cursor.execute("SELECT COUNT(*) FROM meat_trace_processingunit")
    pu_count = cursor.fetchone()[0]
    print(f"\nProcessing Units: {pu_count}")

    if pu_count > 0:
        cursor.execute("SELECT id, name, location FROM meat_trace_processingunit LIMIT 5")
        pus = cursor.fetchall()
        print("Sample processing units:")
        for pu in pus:
            print(f"  ID: {pu[0]}, Name: {pu[1]}, Location: {pu[2]}")

    # Check animals
    cursor.execute("SELECT COUNT(*) FROM meat_trace_animal")
    animal_count = cursor.fetchone()[0]
    print(f"\nAnimals: {animal_count}")

    if animal_count > 0:
        cursor.execute("SELECT id, animal_id, species, farmer_id, slaughtered, transferred_to_id FROM meat_trace_animal LIMIT 5")
        animals = cursor.fetchall()
        print("Sample animals:")
        for animal in animals:
            print(f"  ID: {animal[0]}, Animal ID: {animal[1]}, Species: {animal[2]}, Farmer: {animal[3]}, Slaughtered: {animal[4]}, Transferred to: {animal[5]}")

    # Check products
    cursor.execute("SELECT COUNT(*) FROM meat_trace_product")
    product_count = cursor.fetchone()[0]
    print(f"\nProducts: {product_count}")

    if product_count > 0:
        cursor.execute("SELECT id, name, product_type, processing_unit_id, animal_id FROM meat_trace_product LIMIT 5")
        products = cursor.fetchall()
        print("Sample products:")
        for product in products:
            print(f"  ID: {product[0]}, Name: {product[1]}, Type: {product[2]}, Processing Unit: {product[3]}, Animal: {product[4]}")

    # Check orders
    cursor.execute("SELECT COUNT(*) FROM meat_trace_order")
    order_count = cursor.fetchone()[0]
    print(f"\nOrders: {order_count}")

    if order_count > 0:
        cursor.execute("SELECT id, customer_id, shop_id, status, total_amount FROM meat_trace_order LIMIT 5")
        orders = cursor.fetchall()
        print("Sample orders:")
        for order in orders:
            print(f"  ID: {order[0]}, Customer: {order[1]}, Shop: {order[2]}, Status: {order[3]}, Amount: {order[4]}")

    # Check processing unit users
    cursor.execute("SELECT COUNT(*) FROM meat_trace_processingunituser")
    pu_user_count = cursor.fetchone()[0]
    print(f"\nProcessing Unit Users: {pu_user_count}")

    if pu_user_count > 0:
        cursor.execute("SELECT user_id, processing_unit_id, role, is_active FROM meat_trace_processingunituser LIMIT 5")
        pu_users = cursor.fetchall()
        print("Sample processing unit users:")
        for pu_user in pu_users:
            print(f"  User: {pu_user[0]}, Processing Unit: {pu_user[1]}, Role: {pu_user[2]}, Active: {pu_user[3]}")

    conn.close()
else:
    print(f"Database file {db_path} not found")