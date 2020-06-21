from rest_framework import serializers
from latex.models import LatexImage


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
            # Drop any fields that are not specified in the `fields` argument.
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

