What I changed:

- Added `gender` (choices: male, female, unknown) and `notes` (optional text) to `meat_trace.models.Animal`.
- Exposed `gender` and `notes` in `meat_trace.serializers.AnimalSerializer`.

Required next steps (run on your development machine):

1. Create and apply Django migrations:

   # Activate your virtualenv if needed
   python manage.py makemigrations meat_trace
   python manage.py migrate

2. If you use Docker, rebuild and apply migrations inside the container.

3. Run tests and/or start the dev server and test the Register Animal flow from the app.

Notes:
- The backend will default `gender='unknown'` when not provided.
- Frontend now sends `gender` and `notes` in the create payload. If you prefer different defaults or stricter validation for `health_status` or `gender`, update the model/serializer accordingly.

If you'd like, I can generate a migration file here, but it's safer to run `makemigrations` in your environment to ensure correct migration numbering and app configs.