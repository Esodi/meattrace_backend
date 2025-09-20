import sqlite3
import os

# Connect to the database
db_path = 'db.sqlite3'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check the animal table schema
    cursor.execute("PRAGMA table_info(meat_trace_animal)")
    columns = cursor.fetchall()

    print("Animal table schema:")
    for column in columns:
        print(f"  {column[1]}: {column[2]} (nullable: {column[3]})")

    # Check if animal_name column exists
    column_names = [col[1] for col in columns]
    if 'animal_name' in column_names:
        print("\n[SUCCESS] animal_name column exists")
    else:
        print("\n[ERROR] animal_name column is missing")

    conn.close()
else:
    print(f"Database file {db_path} not found")