
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("SELECT id, farmer_id FROM meat_trace_animal WHERE id = 1")
    row = cursor.fetchone()
    print(f"Row 1 raw: {row}")
    
    # It seems row[1] is indeed the string 'abbatoir_id'
    # Let's just smash it with a valid ID (e.g. 1)
    
    cursor.execute("UPDATE meat_trace_animal SET farmer_id = 1 WHERE id = 1")
    print("Forced update of row 1 to farmer_id = 1")
    
    cursor.execute("SELECT id, farmer_id FROM meat_trace_animal WHERE id = 1")
    row = cursor.fetchone()
    print(f"Row 1 after fix: {row}")
