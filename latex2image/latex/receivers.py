from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured

from rest_framework.authtoken.models import Token

from latex.models import LatexImage
from latex.api import get_field_cache_key


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

    try:
        import django.core.cache as cache
    except ImproperlyConfigured:
        return

    def_cache = cache.caches["default"]

    def_cache.delete(instance.tex_key)

    for attr in ("creation_time", "data_url", "compile_error", "creator"):
        def_cache.delete(get_field_cache_key(instance.tex_key, attr))


@receiver(post_save, sender=LatexImage)
def create_image_cache_on_save(sender, instance, **kwargs):
    # We will cache image and data_url
    try:
        import django.core.cache as cache
    except ImproperlyConfigured:
        return

    def_cache = cache.caches["default"]

    from django.conf import settings

    if instance.image:
        cache_image_relative_path = getattr(
            settings, "L2I_API_IMAGE_RETURNS_RELATIVE_PATH", True)
        if cache_image_relative_path:
            image_cache_value = str(instance.image)
        else:
            image_cache_value = instance.image.url

        def_cache.add(instance.tex_key, image_cache_value, None)

    other_attr_to_cache = ["compile_error"]

    if getattr(settings, "L2I_CACHE_DATA_URL_ON_SAVE", False):
        other_attr_to_cache.append("data_url")

    for attr in other_attr_to_cache:
        attr_value = getattr(instance, attr)
        if len(str(attr_value)) <= getattr(settings, "L2I_CACHE_MAX_BYTES", 0):
            def_cache.add(get_field_cache_key(instance.tex_key, "data_url"), attr_value, None)
