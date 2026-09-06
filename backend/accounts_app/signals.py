from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_gullak_account_for_new_user(sender, instance, created, **kwargs):
    """Every user gets exactly one Gullak account, auto-created and never user-deletable."""
    if not created:
        return
    from wallet.services import get_or_create_gullak
    get_or_create_gullak(instance)
