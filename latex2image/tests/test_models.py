from django.test import TestCase
from latex.models import LatexImage
from django.core.exceptions import ValidationError

from tests.base_test_mixins import get_fake_data_url
from tests import factories


class LatexImageModelTest(TestCase):
    def test_clean_both_dataurl_and_compile_error(self):
        a = LatexImage(
            tex_key="foo",
            data_url=get_fake_data_url("foob="),
            compile_error="some error"
        )
        with self.assertRaises(ValidationError):
            a.save()

    def test_clean_neither_dataurl_nor_compile_error(self):
        a = LatexImage(
            tex_key="foo",
        )
        with self.assertRaises(ValidationError):
            a.save()

    def test_delete_image_file_deleted(self):
        instance = factories.LatexImage()
        import os
        self.assertTrue(
            os.path.isfile(instance.image.path))

        instance.delete()
        self.assertFalse(os.path.isfile(instance.image.path))
