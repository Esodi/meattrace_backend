
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("PRAGMA table_info(meat_trace_animal)")
    columns = cursor.fetchall()
    print("Columns in meat_trace_animal:")
    for col in columns:
        print(col)
