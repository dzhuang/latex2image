from django.core.exceptions import ValidationError
from django.test import TestCase
from tests.base_test_mixins import get_fake_data_url

from latex.models import LatexImage


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
