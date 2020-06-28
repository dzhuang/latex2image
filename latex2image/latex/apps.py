from django.apps import AppConfig


class Latex2ImageConfig(AppConfig):
    name = 'latex'

    def ready(self):
        import latex.receivers  # noqa
        from latex.checks import register_startup_checks

        # register checks
        register_startup_checks()
