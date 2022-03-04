from __future__ import annotations, division

__copyright__ = "Copyright (C) 2020 Dong Zhuang"

__license__ = """
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

from copy import deepcopy

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import JSONParser
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from latex.converter import LatexCompileError, tex_to_img_converter
from latex.models import UPLOAD_TO, LatexImage
from latex.serializers import (LatexImageCreateDataSerialzier,
                               LatexImageSerializer)


class L2IRenderer(JSONRenderer):
    """ If response contains "compile_error", always return 400 """

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if renderer_context:
            response = renderer_context['response']
            if isinstance(data, dict):
                compile_error = data.get("compile_error", None)
                if compile_error is not None:
                    response.status_code = status.HTTP_400_BAD_REQUEST
                else:
                    # remove compile_error from data if it's None
                    data.pop("compile_error", None)
        return super().render(data, accepted_media_type, renderer_context)


def get_field_cache_key(tex_key, field_name):
    return "%s:%s" % (tex_key, field_name)


def get_cached_attribute_by_tex_key(tex_key, attr, request):
    try:
        import django.core.cache as cache

        def_cache = cache.caches["default"]
        cache_key = get_field_cache_key(tex_key, attr)
    except ImproperlyConfigured:
        cache_key = None

    result_dict = {}

    if cache_key is not None:
        # def_cache.delete(cache_key)
        ret_value = def_cache.get(cache_key)

        if ret_value is not None:
            # print("Got value in cache!")
            result_dict[attr] = ret_value
            return result_dict

        compile_error_cache_key = get_field_cache_key(tex_key, "compile_error")
        cached_compile_error = def_cache.get(compile_error_cache_key)
        if cached_compile_error is not None:
            return {"compile_error": cached_compile_error}

    # Check db if it exists
    objs = LatexImage.objects.filter(tex_key=tex_key)
    if not objs.count():
        return None if request.method == "POST" else {}

    obj = objs[0]

    serializer = LatexImageSerializer(obj, fields=attr, context={"request": request})

    data = serializer.to_representation(obj)

    compile_error = data.pop("compile_error", None)
    if compile_error is not None:
        result_dict["compile_error"] = compile_error

        if cache_key is not None:
            compile_error_cache_key = get_field_cache_key(tex_key, "compile_error")
            def_cache.add(compile_error_cache_key, obj.compile_error, None)
        return result_dict

    ret_value = data.get(attr, None)
    if ret_value is None:
        return None if request.method == "POST" else {}

    assert isinstance(ret_value, str)

    # Ignore attribute value with size (byte) over L2I_CACHE_MAX_BYTES
    if (cache_key is not None
            and len(ret_value) <= getattr(settings, "L2I_CACHE_MAX_BYTES", 0)):
        def_cache.add(cache_key, ret_value, None)

    result_dict[attr] = ret_value
    return result_dict


class CreateMixin:
    def create(self, request, *args, **kwargs):
        req_params = JSONParser().parse(request)
        req_params_copy = deepcopy(req_params)
        data_serializer = LatexImageCreateDataSerialzier(data=req_params)

        try:
            data_serializer.is_valid(raise_exception=True)
        except Exception as e:
            from traceback import print_exc
            print_exc()
            raise e

        data = data_serializer.data

        fields = data.get("fields")
        tex_key = data.get("tex_key")

        if fields and len(fields) == 1 and tex_key is not None:
            # Try to get cached result
            cached_result = (
                get_cached_attribute_by_tex_key(tex_key, fields[0], request))
            if cached_result:
                return Response(cached_result, status=status.HTTP_200_OK)
            else:
                # No cached result, re validate the request data
                req_params_copy.pop("fields")
                req_params_copy.pop("tex_key")
                _serializer = LatexImageCreateDataSerialzier(data=req_params_copy)
                try:
                    _serializer.is_valid(raise_exception=True)
                except ValidationError as e:
                    msg = _("No cache found, you need to supply required fields "
                            "to regenerate the image. ")
                    raise ValidationError(detail=f"{msg}{e.detail}")

        data_url = None
        error = None

        image_format = data["image_format"]
        fields = data.pop("fields", None)
        use_storage_file_if_exists = data.pop(
            "use_storage_file_if_exists",
            getattr(
                settings, "L2I_USE_EXISTING_STORAGE_IMAGE_TO_CREATE_INSTANCE",
                False))

        try:
            _converter = tex_to_img_converter(**data)
        except Exception as e:
            return Response(
                {"error": f"{type(e).__name__}: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST)

        qs = LatexImage.objects.filter(tex_key=_converter.tex_key)
        instance = None

        if qs.count():
            instance = qs[0]
        else:
            if use_storage_file_if_exists:
                # Set Django's FileField to an existing file
                # https://stackoverflow.com/a/10906037/3437454
                _path = "/".join(
                    [UPLOAD_TO, ".".join([_converter.tex_key, image_format])])
                if default_storage.exists(_path):
                    with transaction.atomic():
                        instance = LatexImage(
                            tex_key=_converter.tex_key,
                            creator=self.request.user
                        )
                        instance.image = _path
                        instance.save()

        if instance:
            image_serializer = self.get_serializer(instance, fields=fields)
            return Response(
                image_serializer.data, status=status.HTTP_200_OK)

        try:
            data_url = _converter.get_converted_data_url()
        except Exception as e:
            error = f"{type(e).__name__}: {str(e)}"
            if not isinstance(e, LatexCompileError):
                return Response(
                    {"error": error},
                    status=status.HTTP_400_BAD_REQUEST)

        assert not all([data_url is None, error is None])

        data = {"tex_key": _converter.tex_key}
        if data_url is not None:
            data["data_url"] = data_url
        else:
            data["compile_error"] = error

        data["creator"] = self.request.user.pk

        image_serializer = self.get_serializer(data=data)

        if image_serializer.is_valid():
            instance = image_serializer.save()
            return Response(
                self.get_serializer(instance, fields=fields).data,
                status=status.HTTP_201_CREATED)
        return Response(
            # For example, tex_key already exists.
            image_serializer.errors,
            status=status.HTTP_400_BAD_REQUEST)


class LatexImageCreate(
        CreateMixin, generics.CreateAPIView):
    renderer_classes = (L2IRenderer,)
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LatexImageSerializer


class FieldsSerializerMixin:
    def get_serializer(self, *args, **kwargs):
        fields = self.request.GET.getlist('fields')
        if fields:
            kwargs["fields"] = fields[0]
        return super().get_serializer(*args, **kwargs)


class LatexImageDetail(
        FieldsSerializerMixin, generics.RetrieveUpdateDestroyAPIView):
    renderer_classes = (L2IRenderer,)
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LatexImageSerializer

    lookup_field = "tex_key"

    def get_queryset(self):
        if not self.request.user.is_superuser:
            return LatexImage.objects.filter(creator=self.request.user)
        return LatexImage.objects.all()

    def get(self, request, *args, **kwargs):
        tex_key = kwargs.get("tex_key")
        assert tex_key is not None
        fields = request.GET.getlist('fields')
        if len(fields) == 1:
            fields = fields[0].split(",")
            if len(fields) == 1:
                cached_result = (
                    get_cached_attribute_by_tex_key(
                        tex_key, fields[0], request))
                return Response(
                    data=cached_result,
                    status=status.HTTP_200_OK)
        return super().get(request, *args, **kwargs)


class LatexImageList(
        CreateMixin, FieldsSerializerMixin, generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LatexImageSerializer
    renderer_classes = (L2IRenderer,)

    def get_queryset(self):
        if not self.request.user.is_superuser:
            return LatexImage.objects.filter(creator=self.request.user)
        return LatexImage.objects.all()
