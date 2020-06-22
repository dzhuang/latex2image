from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from rest_framework.authtoken.models import Token

from latex.models import LatexImage


@receiver(post_save, sender=get_user_model())
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created or getattr(instance, 'from_admin_site', False):
        Token.objects.create(user=instance)


@receiver(post_delete, sender=LatexImage)
def image_delete(sender, instance, **kwargs):
    """
    Delete the associated image when the instance is deleted.
    """

    # “false” to instance.image.delete ensures that ImageField
    # does not save the model
    # post_delete signal is sent at the end of a model’s delete()
    # method and a queryset’s delete() method.
    # This is safer as it does not execute unless the parent object
    # is successfully deleted.
    instance.image.delete(False)
