from __future__ import division

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

import sys

from urllib.parse import urljoin

from django.core.exceptions import ImproperlyConfigured
from django.db.models.fields.files import ImageFieldFile
from django.conf import settings
from django.utils.encoding import filepath_to_uri
from django.db.transaction import atomic

from rest_framework.parsers import JSONParser
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer

from latex.models import LatexImage
from latex.serializers import LatexImageSerializer
from latex.converter import (
    tex_to_img_converter, LatexCompileError, )


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


def get_cached_attribute_by_tex_key(tex_key, attr, request=None):
    if attr != getattr(settings, "L2I_API_CACHE_FIELD", None):
        return {}

    try:
        import django.core.cache as cache

        def_cache = cache.caches["default"]
        cache_key = tex_key
        error_key = "%s_error" % cache_key
    except ImproperlyConfigured:
        return None

    assert cache_key is not None

    result_dict = {}

    def update_image(_result_dict, _request):
        # When image is requested to be cached, make sure image url is
        # an absolute url irrespective of MEDIA_URL changes.
        if "image" in _result_dict and _request is not None:
            image_dict = _result_dict["image"]
            assert isinstance(image_dict, dict), image_dict
            _result_dict["image"]["url"] = (
                request.build_absolute_uri(
                    urljoin(
                        settings.MEDIA_URL,
                        filepath_to_uri(
                            _result_dict["image"]["url"]))
                ))

    attr_value = def_cache.get(cache_key)
    compile_error_key = def_cache.get(error_key)

    if attr_value is not None:
        assert compile_error_key is None
        result_dict[attr] = attr_value
        update_image(result_dict, request)
        return result_dict

    elif compile_error_key is not None:
        assert attr_value is None
        result_dict["compile_error"] = compile_error_key
        return result_dict

    # Check db if it exists
    objs = LatexImage.objects.filter(tex_key=tex_key)
    if not objs.count():
        return {}

    obj = objs[0]
    if obj.compile_error:
        result_dict["compile_error"] = obj.compile_error
        def_cache.add(error_key, obj.compile_error, None)
        return result_dict

    attr_value = getattr(obj, attr)

    assert attr_value is not None, \
        "Attribute %s of %s can't be None" % (str(obj), attr)

    # For Image, we cache its url
    if isinstance(attr_value, ImageFieldFile):
        attr_value = {
            "url": str(attr_value),
            "size": attr_value.size
        }

    # ignore attribute value with size (byte) over L2I_CACHE_MAX_BYTES
    if len(repr(attr_value)) <= getattr(settings, "L2I_CACHE_MAX_BYTES", 0):
        def_cache.add(cache_key, attr_value, None)

    result_dict[attr] = attr_value
    update_image(result_dict, request)
    return result_dict


def get_cached_results_from_request_field_and_tex_key(request, tex_key, field_str):
    """
    This currently deal with single field ('image' or 'data_url') cache
    """
    cached_result = None
    fields = field_str.split(",")
    if len(fields) == 1:
        cached_result = get_cached_attribute_by_tex_key(
            tex_key, fields[0], request=request)
    return cached_result


class CreateMixin:
    def create(self, request, *args, **kwargs):
        try:
            req_params = JSONParser().parse(request)
            compiler = req_params.pop("compiler")
            tex_source = req_params.pop("tex_source")
            image_format = req_params.pop("image_format")
            tex_key = req_params.pop("tex_key", None)
            field_str = req_params.pop("fields", None)
        except Exception:
            from traceback import print_exc
            print_exc()
            tp, e, __ = sys.exc_info()
            error = "%s: %s" % (tp.__name__, str(e))
            return Response(
                {"error": error},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if field_str and tex_key:
            cached_result = (
                get_cached_results_from_request_field_and_tex_key(
                    request, tex_key, field_str))
            if cached_result:
                return Response(cached_result,
                                status=status.HTTP_200_OK)

        data_url = None
        error = None

        try:
            _converter = tex_to_img_converter(
                compiler, tex_source, image_format, tex_key, **req_params)
        except Exception as e:
            from traceback import print_exc
            print_exc()
            tp, e, __ = sys.exc_info()
            error = "%s: %s" % (tp.__name__, str(e))
            return Response(
                {"error": error},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        qs = LatexImage.objects.filter(tex_key=_converter.tex_key)
        if qs.count():
            instance = qs[0]
            image_serializer = self.get_serializer(
                instance, fields=field_str)
            return Response(
                image_serializer.data, status=201)

        try:
            data_url = _converter.get_converted_data_url()
        except Exception as e:
            if isinstance(e, LatexCompileError):
                error = "%s: %s" % (type(e).__name__, str(e))
            else:
                from traceback import print_exc
                print_exc()
                tp, e, __ = sys.exc_info()
                error = "%s: %s" % (tp.__name__, str(e))
                return Response(
                    {"error": error},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        assert not all([data_url is None, error is None])

        data = {"tex_key": _converter.tex_key}
        if data_url is not None:
            data["data_url"] = data_url
        else:
            data["compile_error"] = error

        data["creator"] = self.request.user.pk

        image_serializer = self.get_serializer(data=data)

        if image_serializer.is_valid():
            with atomic():
                instance = image_serializer.save()
            return Response(
                self.get_serializer(instance, fields=field_str).data,
                status=status.HTTP_201_CREATED)
        return Response(
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
        fields_str = request.GET.getlist('fields')
        if len(fields_str) == 1:
            fields = fields_str[0].split(",")
            if len(fields) == 1:
                cached_result = (
                    get_cached_results_from_request_field_and_tex_key(
                        request, tex_key, fields[0]))
                if cached_result is not None:
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
