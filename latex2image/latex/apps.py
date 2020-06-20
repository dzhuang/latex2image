from django.apps import AppConfig


class LatexConfig(AppConfig):
    name = 'latex'

    def ready(self):
        import latex.receivers  # noqa
        from latex.checks import register_startup_checks

        # register checks
        register_startup_checks()
