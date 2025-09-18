# MeatTrace Backend

A Django REST API for meat traceability management.

## Setup Instructions

1. Ensure Python 3.8+ is installed.

2. Clone or navigate to the project directory.

3. Create a virtual environment:
   ```
   python3 -m venv venv
   ```

4. Activate the virtual environment:
   - On Linux/Mac: `source venv/bin/activate`
   - On Windows: `venv\Scripts\activate`

5. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

6. Run migrations:
   ```
   python manage.py migrate
   ```

7. Create a superuser (optional, for admin access):
   ```
   python manage.py createsuperuser
   ```

8. Run the development server:
   ```
   python manage.py runserver
   ```

The API will be available at `http://127.0.0.1:8000/`.

## API Documentation

### Endpoints

- `GET /api/v1/meattrace/` - List all meat traces (with pagination, filtering, search)
- `POST /api/v1/meattrace/` - Create a new meat trace
- `GET /api/v1/meattrace/{id}/` - Retrieve a specific meat trace
- `PUT /api/v1/meattrace/{id}/` - Update a specific meat trace
- `DELETE /api/v1/meattrace/{id}/` - Delete a specific meat trace

### Filtering and Search

- Filter by status: `?status=pending`
- Filter by origin: `?origin=USA`
- Search: `?search=batch123`

### Example API Calls

#### Create a Meat Trace
```bash
curl -X POST http://127.0.0.1:8000/api/v1/meattrace/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Beef Steak",
    "origin": "Argentina",
    "batch_number": "BATCH001",
    "status": "pending"
  }'
```

#### List Meat Traces
```bash
curl http://127.0.0.1:8000/api/v1/meattrace/
```

#### Update a Meat Trace
```bash
curl -X PUT http://127.0.0.1:8000/api/v1/meattrace/1/ \
  -H "Content-Type: application/json" \
  -d '{"status": "processed"}'
```

## Admin Interface

Access the Django admin at `http://127.0.0.1:8000/admin/` using the superuser credentials.

## Authentication

The API uses Token Authentication. To obtain a token:

1. Create a user via admin or API.
2. Use the token in the Authorization header: `Authorization: Token <your-token>`

## CORS

CORS is enabled for cross-origin requests from the Flutter app.