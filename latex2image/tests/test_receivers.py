from django.conf import settings
from django.test import TestCase, override_settings

from tests import factories
from tests.base_test_mixins import (
    L2ITestMixinBase, improperly_configured_cache_patch)

from latex.models import LatexImage
from latex.api import get_field_cache_key
from latex.serializers import LatexImageSerializer


class LatexImageReceiversTest(L2ITestMixinBase, TestCase):
    @override_settings(
        L2I_CACHE_DATA_URL_ON_SAVE=False, L2I_API_IMAGE_RETURNS_RELATIVE_PATH=True)
    def test_image_create_image_relative_path_cached(self):
        instance = factories.LatexImageFactory()

        self.assertIsNotNone(
            self.test_cache.get(
                get_field_cache_key(instance.tex_key, "image")))

        self.assertEqual(self.test_cache.get(
            get_field_cache_key(instance.tex_key, "image")),
            str(instance.image))

        self.assertIsNone(
            self.test_cache.get(
                get_field_cache_key(instance.tex_key, "data_url")))

        self.assertIsNone(
            self.test_cache.get(
                get_field_cache_key(instance.tex_key, "compile_error")))

    @override_settings(
        L2I_CACHE_DATA_URL_ON_SAVE=False, L2I_API_IMAGE_RETURNS_RELATIVE_PATH=False)
    def test_image_create_image_url_not_cached(self):
        instance = factories.LatexImageFactory()

        self.assertIsNone(
            self.test_cache.get(
                get_field_cache_key(instance.tex_key, "image")))

        self.assertIsNone(
            self.test_cache.get(
                get_field_cache_key(instance.tex_key, "data_url")))

        self.assertIsNone(
            self.test_cache.get(
                get_field_cache_key(instance.tex_key, "compile_error")))

    @override_settings(L2I_CACHE_DATA_URL_ON_SAVE=True)
    def test_image_create_image_url_not_cached(self):
        instance = factories.LatexImageFactory()

        self.assertIsNotNone(
            self.test_cache.get(
                get_field_cache_key(instance.tex_key, "data_url"),
                instance.data_url))

        self.assertIsNone(
            self.test_cache.get(
                get_field_cache_key(instance.tex_key, "compile_error")))

    def test_image_create_compile_error_cached(self):
        instance = factories.LatexImageErrorFactory()

        self.assertIsNone(
            self.test_cache.get(
                get_field_cache_key(instance.tex_key, "image")))

        self.assertIsNotNone(
            self.test_cache.get(
                get_field_cache_key(instance.tex_key, "compile_error"),
                instance.compile_error))

    def test_delete_image_file_deleted(self):
        instance = factories.LatexImageFactory()

        import os
        upload_to, file_name = os.path.split(str(instance.image))
        file_path = os.path.join(settings.MEDIA_ROOT, upload_to, file_name)
        self.assertTrue(os.path.isfile(file_path))

        instance.delete()
        self.assertFalse(os.path.isfile(file_path))

    def test_delete_image_cache_deleted(self):
        instance = factories.LatexImageFactory()

        serializer = LatexImageSerializer(instance)
        data = serializer.to_representation(instance)

        creator_cache_key = get_field_cache_key(instance.tex_key, "creator")
        self.test_cache.add(creator_cache_key, data["creator"])
        self.assertEqual(self.test_cache.get(creator_cache_key), data["creator"])

        creation_time_cache_key = get_field_cache_key(
            instance.tex_key, "creation_time")
        self.test_cache.add(creation_time_cache_key, data["creation_time"])
        self.assertEqual(
            self.test_cache.get(creation_time_cache_key), data["creation_time"])

        instance.delete()
        self.assertIsNone(self.test_cache.get(creation_time_cache_key))
        self.assertIsNone(
            self.test_cache.get(
                get_field_cache_key(instance.tex_key, "compile_error")))

    def test_delete_image_compile_error_cache_deleted(self):
        instance = factories.LatexImageErrorFactory()

        instance.delete()
        self.assertIsNone(
            self.test_cache.get(
                get_field_cache_key(instance.tex_key, "compile_error")))

    def test_cache_improperly_configured_works(self):
        with improperly_configured_cache_patch():
            instance1 = factories.LatexImageFactory()
            instance2 = factories.LatexImageErrorFactory()
            self.assertEqual(LatexImage.objects.all().count(), 2)

            instance1.delete()
            instance2.delete()
            self.assertEqual(LatexImage.objects.all().count(), 0)
