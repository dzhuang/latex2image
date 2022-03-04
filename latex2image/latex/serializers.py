from django.conf import settings
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from latex.constants import (ALLOWED_COMPILER,
                             ALLOWED_COMPILER_FORMAT_COMBINATION,
                             ALLOWED_LATEX2IMG_FORMAT)
from latex.models import LatexImage

LATEX_IMAGE_ALLOWED_FIELDS_NAME = [f.name for f in LatexImage._meta.get_fields()]


class DynamicFieldsModelSerializer(serializers.ModelSerializer):
    """
    A ModelSerializer that takes an additional `fields` argument that
    controls which fields should be displayed.

    https://www.django-rest-framework.org/api-guide/serializers/#example
    """

    def __init__(self, *args, **kwargs):
        # Don't pass the 'fields' arg up to the superclass
        fields = kwargs.pop('fields', None)

        # Instantiate the superclass normally
        super().__init__(*args, **kwargs)

        if fields is not None:
            # Drop any fields that are not specified in the `fields` argument
            # but we will always include "compile_error"
            allowed = set(fields.split(",") + ["compile_error"])
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name)


class LatexImageSerializer(DynamicFieldsModelSerializer):

    class Meta:
        model = LatexImage
        fields = ("id",
                  "tex_key",
                  "creation_time",
                  "data_url",
                  "image",
                  "compile_error",
                  "creator",
                  )

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if not getattr(settings, "L2I_API_IMAGE_RETURNS_RELATIVE_PATH", True):
            return representation

        if "image" in representation and representation["image"] is not None:
            representation['image'] = str(instance.image)
        return representation


class LatexImageCreateDataSerialzier(serializers.Serializer):
    compiler = serializers.ChoiceField(
        required=False, allow_null=True, choices=ALLOWED_COMPILER)
    image_format = serializers.ChoiceField(
        required=False, allow_null=True, choices=ALLOWED_LATEX2IMG_FORMAT)
    tex_source = serializers.CharField(max_length=None, required=False)
    tex_key = serializers.CharField(max_length=None, required=False)
    fields = serializers.CharField(max_length=None, required=False)
    use_storage_file_if_exists = serializers.BooleanField(
        required=False,
        default=getattr(
            settings, "L2I_USE_EXISTING_STORAGE_IMAGE_TO_CREATE_INSTANCE", False))

    def validate_fields(self, fields_data):
        if fields_data is None:
            return []
        fields = [f.strip() for f in fields_data.split(",")]
        unknown = []
        for f in fields:
            if f not in LATEX_IMAGE_ALLOWED_FIELDS_NAME:
                unknown.append(f)

        if unknown:
            raise serializers.ValidationError(
                _("Unknown field name: {unknown}, allowed are {allowed}").format(
                    unknown=unknown,
                    allowed=LATEX_IMAGE_ALLOWED_FIELDS_NAME
                )
            )
        return fields

    def validate(self, attrs):

        fields = attrs.get("fields")
        tex_key = attrs.get("tex_key")

        # Only when fields and tex_key presents, a create api view
        # has the chance to get the cached results
        may_get_cached_results_by_fields_and_tex_key = (
            fields and len(fields) == 1 and tex_key
        )

        if not may_get_cached_results_by_fields_and_tex_key:
            missing_fields = []
            for field in ["compiler", "tex_source", "image_format"]:
                if attrs.get(field) is None:
                    missing_fields.append(field)

            if missing_fields:
                raise serializers.ValidationError(
                    _("These fields are required {missing_fields}").format(
                        missing_fields=missing_fields
                    )
                )

        compiler = attrs.get("compiler")
        image_format = attrs.get("image_format")
        if compiler is not None and image_format is not None:
            if (compiler, image_format) not in ALLOWED_COMPILER_FORMAT_COMBINATION:
                raise serializers.ValidationError(
                    _('Combination ("{compiler}", "{image_format}") not supported, '
                      'allowed combinations are {allowed}').format(
                        compiler=compiler,
                        image_format=image_format,
                        allowed=", ".join(
                            [str(comb) for comb
                             in ALLOWED_COMPILER_FORMAT_COMBINATION])
                    )
                )

        return attrs
