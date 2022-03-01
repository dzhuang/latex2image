from django.apps import AppConfig


class Latex2ImageConfig(AppConfig):
    name = 'latex'
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        import latex.receivers  # noqa
        from latex.checks import register_startup_checks

        # register checks
        register_startup_checks()
