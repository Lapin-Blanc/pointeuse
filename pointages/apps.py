from django.apps import AppConfig


class PointagesConfig(AppConfig):
    name = 'pointages'
    verbose_name = "Pointage Max"
    default_auto_field = 'django.db.models.AutoField'

    def ready(self):
        from . import signals  # noqa: F401
