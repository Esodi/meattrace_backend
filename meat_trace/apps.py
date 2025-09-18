from django.apps import AppConfig


class MeatTraceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'meat_trace'

    def ready(self):
        import meat_trace.signals  # noqa
