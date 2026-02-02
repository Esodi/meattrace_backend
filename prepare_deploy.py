
import os
import django
import sys

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from django.db import connection, transaction
from meat_trace.models import User

def fix_bad_farmer_ids():
    print("Checking for invalid farmer_id values in meat_trace_animal...")
    with connection.cursor() as cursor:
        # Check database type
        db_engine = connection.settings_dict['ENGINE']
        print(f"Database engine: {db_engine}")

        # 1. Fix non-integer values (SQLite specific usually)
        if 'sqlite' in db_engine:
            cursor.execute("SELECT id, farmer_id FROM meat_trace_animal")
            rows = cursor.fetchall()
            bad_rows = []
            for row in rows:
                try:
                    int(row[1])
                except (ValueError, TypeError):
                    bad_rows.append(row)
            
            if bad_rows:
                print(f"Found {len(bad_rows)} rows with non-integer farmer_id: {bad_rows}")
                # Assign to admin or first valid user
                valid_user = User.objects.filter(is_superuser=True).first() or User.objects.first()
                if valid_user:
                    print(f"Reassigning to user {valid_user.id} ({valid_user.username})")
                    for row in bad_rows:
                        cursor.execute("UPDATE meat_trace_animal SET farmer_id = %s WHERE id = %s", [valid_user.id, row[0]])
                    print("Fixed non-integer rows.")
                else:
                    print("No valid user found to reassign! Deleting bad rows.")
                    ids = [r[0] for r in bad_rows]
                    cursor.execute(f"DELETE FROM meat_trace_animal WHERE id IN ({','.join(map(str, ids))})")

        # 2. Fix orphaned FKs (valid integers but user doesn't exist)
        cursor.execute("""
            SELECT id, farmer_id FROM meat_trace_animal 
            WHERE farmer_id NOT IN (SELECT id FROM auth_user)
        """)
        orphans = cursor.fetchall()
        
        if orphans:
            print(f"Found {len(orphans)} orphaned animals (farmer_id checks): {orphans}")
            valid_user = User.objects.filter(is_superuser=True).first() or User.objects.first()
            if valid_user:
                 # Reassign
                 ids = [r[0] for r in orphans]
                 # Use a loop or bulk update depending on DB, loop is safer for cross-db script simplicity here
                 for oid, _ in orphans:
                     cursor.execute("UPDATE meat_trace_animal SET farmer_id = %s WHERE id = %s", [valid_user.id, oid])
                 print("Reassigned orphaned rows.")
            else:
                print("No valid user to reassign. Deleting orphans.")
                ids = [r[0] for r in orphans]
                cursor.execute(f"DELETE FROM meat_trace_animal WHERE id IN ({','.join(map(str, ids))})")
        else:
            print("No orphaned FKs found.")

if __name__ == "__main__":
    try:
        fix_bad_farmer_ids()
        print("Data check complete. Ready for migration.")
    except Exception as e:
        print(f"An error occurred: {e}")
        # If table doesn't exist or column renamed already, it might fail, which is fine
        print("Note: If the migration is already applied, this script failing is expected.")
