from django.apps import AppConfig


class AccountsAppConfig(AppConfig):
    name = 'accounts_app'

    def ready(self):
        from . import signals  # noqa: F401 — registers the post_save receiver
