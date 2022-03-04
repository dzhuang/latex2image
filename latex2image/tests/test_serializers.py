from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from latex.serializers import LatexImageCreateDataSerialzier


class LatexImageCreateDataSerializerTest(SimpleTestCase):
    serializer = LatexImageCreateDataSerialzier

    def test_ok(self):
        data = dict(
            compiler="xelatex",
            image_format="png",
            tex_source="foobar",
            fields="image,data_url"
        )
        serializer = self.serializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_fields_unknown(self):
        data = dict(
            compiler="xelatex",
            image_format="png",
            tex_source="foobar",
            fields="image,data"
        )
        serializer = self.serializer(data=data)
        with self.assertRaises(ValidationError) as cm:
            serializer.is_valid(raise_exception=True)
        self.assertIn('Unknown field name: "data"', str(cm.exception))

    def test_fields_not_string(self):
        data = dict(
            compiler="xelatex",
            image_format="png",
            tex_source="foobar",
            fields=1000
        )
        serializer = self.serializer(data=data)
        with self.assertRaises(ValidationError) as cm:
            serializer.is_valid(raise_exception=True)
        self.assertIn("This field should be a string", str(cm.exception))

    def test_get_cached_results_allowed_missing_fields_is_ok(self):
        data = dict(
            fields="image",
            tex_key="foobar"
        )
        serializer = self.serializer(data=data)
        self.assertTrue(serializer.is_valid(raise_exception=True))

    def test_get_cached_results_not_allowed_missing_one_field_error(self):
        data = dict(
            compiler="xelatex",
            image_format="png",
            fields="image,data_url",
            tex_key="foobar"
        )

        expected_message = "This field is required"

        serializer = self.serializer(data=data)
        with self.assertRaises(ValidationError) as cm:
            serializer.is_valid(raise_exception=True)
        self.assertIn(expected_message, str(cm.exception))

    def test_get_cached_results_not_allowed_missing_multiple_fields_error(self):
        data = dict(
            fields="image,data_url",
            tex_key="foobar"
        )

        expected_message = (
            'These fields are required "compiler", "tex_source", "image_format"')

        serializer = self.serializer(data=data)
        with self.assertRaises(ValidationError) as cm:
            serializer.is_valid(raise_exception=True)
        self.assertIn(expected_message, str(cm.exception))
