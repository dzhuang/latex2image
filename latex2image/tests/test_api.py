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


import json
import os
from unittest import mock
from random import randint

from django.test import TestCase, override_settings
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from tests import factories
from tests.base_test_mixins import (
    L2ITestMixinBase, get_latex_file_dir, get_fake_data_url,
    suppress_stdout_decorator,
    improperly_configured_cache_patch
)
from latex.models import LatexImage
from latex.api import LatexImageList
from latex.converter import get_data_url

IMAGE_PATH_PREFIX = "l2i_images/"


class APITestBaseMixin(L2ITestMixinBase, TestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(user=self.test_user)

    @staticmethod
    def get_post_data(file_dir="xelatex", **kwargs):
        doc_folder_path = get_latex_file_dir(file_dir)
        file_path = os.path.join(
            doc_folder_path, os.listdir(doc_folder_path)[0])

        with open(file_path, encoding="utf-8") as f:
            file_data = f.read()

        data = {
            "compiler": "xelatex",
            "tex_source": file_data,
            "image_format": "png",
        }
        data.update(kwargs)
        return data

    def create_n_instances(self, creator=None, n=None):
        creator = creator or self.test_user
        self.n_new = n or randint(3, 20)
        created_objects = factories.LatexImageFactory.create_batch(
            creator=creator, size=self.n_new)
        return created_objects


class LatexListAPITest(APITestBaseMixin, TestCase):
    def test_get_not_authenticated(self):
        self.create_n_instances()
        self.client.force_authenticate(user=None)
        resp = self.client.get(self.get_list_url())
        self.assertEqual(resp.status_code, 401)

    def test_get_success(self):
        self.create_n_instances()

        view = LatexImageList.as_view()
        request = APIRequestFactory().get(self.get_list_url())
        force_authenticate(request, user=self.test_user)
        resp = view(request)
        resp.render()
        self.assertEqual(len(json.loads(resp.content.decode())), self.n_new)
        self.assertEqual(resp.status_code, 200)

    def test_create_success(self):
        self.create_n_instances()
        resp = self.client.post(
            self.get_list_url(), data=self.get_post_data(), format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(LatexImage.objects.all().count(), self.n_new + 1)

    def test_create_already_exist_just_before_saving_success(self):
        instance = factories.LatexImageErrorFactory(tex_key="key_already_exists")
        tex_key = instance.tex_key
        creator = instance.creator
        creation_time = instance.creation_time
        compile_error = instance.compile_error
        instance.delete()

        def get_data_url_side_effect(file_path):
            result = get_data_url(file_path)
            factories.LatexImageErrorFactory(
                tex_key=tex_key, creator=creator,
                creation_time=creation_time, compile_error=compile_error)
            return result

        with mock.patch("latex.converter.get_data_url") as mock_get_data_url:
            mock_get_data_url.side_effect = (
                get_data_url_side_effect)

            resp = self.client.post(
                self.get_list_url(),
                data=self.get_post_data(
                    tex_key=tex_key,
                    creator=creator.pk,
                    compile_error=compile_error,
                ), format='json')
            self.assertEqual(resp.status_code, 500)
            resp_dict = json.loads(resp.content.decode())
            self.assertEqual(resp_dict.get("tex_key", None), ['LaTeXImage with this Tex Key already exists.'])
            self.assertEqual(LatexImage.objects.all().count(), 1)

    def test_no_create_duplicate(self):
        first_object = self.create_n_instances()[0]

        with mock.patch(
                "latex.converter.Tex2ImgBase.get_converted_data_url"
        ) as mock_convert:
            mock_convert.return_value = get_fake_data_url("foob=")
            resp = self.client.post(
                self.get_list_url(),
                data=self.get_post_data(
                    tex_key=first_object.tex_key), format='json')
            mock_convert.assert_not_called()

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(LatexImage.objects.all().count(), self.n_new)

    def test_no_create_duplicate_errored(self):
        tex_key = "what_ever_key"
        factories.LatexImageErrorFactory(tex_key=tex_key, creator=self.test_user)

        with mock.patch(
                "latex.converter.Tex2ImgBase.get_converted_data_url"
        ) as mock_convert:
            mock_convert.return_value = get_fake_data_url("foob=")
            resp = self.client.post(
                self.get_list_url(),
                data=self.get_post_data(tex_key=tex_key), format='json')
            mock_convert.assert_not_called()

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(LatexImage.objects.all().count(), 1)

    @suppress_stdout_decorator(suppress_stderr=True)
    def test_post_data_error_not_compile_error(self):
        post_data = self.get_post_data()
        del post_data["tex_source"]

        resp = self.client.post(
            self.get_list_url(), data=post_data, format='json')
        self.assertContains(resp, "KeyError", status_code=500)
        self.assertEqual(LatexImage.objects.all().count(), 0)

    @suppress_stdout_decorator(suppress_stderr=True)
    def test_converter_init_errored(self):
        resp = self.client.post(
            self.get_list_url(),
            data=self.get_post_data(compiler="latex", image_format="jpg"),
            format="json"
        )
        self.assertEqual(resp.status_code, 500)
        self.assertEqual(LatexImage.objects.all().count(), 0)

    def test_compile_errored(self):
        resp = self.client.post(
            self.get_list_url(),
            data=self.get_post_data(
                file_dir="lualatex", compiler="latex", image_format="png"),
            format="json"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(LatexImage.objects.all().count(), 1)

    @suppress_stdout_decorator(suppress_stderr=True)
    @mock.patch('django.core.files.storage.FileSystemStorage.save')
    def test_errored_but_not_compile_error(self, mock_save):
        exception_str = "this is a custom exception."
        with mock.patch(
                "latex.converter.Tex2ImgBase.get_converted_data_url"
        ) as mock_convert:
            mock_convert.side_effect = RuntimeError(exception_str)
            resp = self.client.post(
                self.get_list_url(),
                data=self.get_post_data(),
                format="json"
            )
        self.assertEqual(resp.status_code, 500)
        self.assertEqual(LatexImage.objects.all().count(), 0)

        # errors are not saved to filesystem
        mock_save.assert_not_called()

    def test_list_owned(self):
        self.create_n_instances()

        another_user = factories.UserFactory()
        n_owned_by_another = randint(10, 20)
        factories.LatexImageFactory.create_batch(
            creator=another_user,
            size=n_owned_by_another)

        resp = self.client.get(self.get_list_url())
        self.assertEqual(
            len(json.loads(resp.content.decode())), self.n_new)
        self.assertEqual(resp.status_code, 200)

    def test_superuser_list_all(self):
        self.create_n_instances()

        another_user = factories.UserFactory()
        n_owned_by_another = randint(10, 20)
        factories.LatexImageFactory.create_batch(
            creator=another_user,
            size=n_owned_by_another)

        self.client.force_authenticate(user=self.superuser)
        resp = self.client.get(self.get_list_url())
        self.assertEqual(
            len(json.loads(resp.content.decode())),
            n_owned_by_another + self.n_new)
        self.assertEqual(resp.status_code, 200)


class LatexDetailAPITest(APITestBaseMixin, TestCase):
    def test_get_not_authenticated(self):
        instance = factories.LatexImageFactory()

        self.client.force_authenticate(user=None)
        resp = self.client.get(
            self.get_detail_url(instance.tex_key))
        self.assertEqual(resp.status_code, 401)

    def test_get_may_not_visit_others_image_except_superuser(self):
        another_user = factories.UserFactory()
        instance = factories.LatexImageFactory(creator=another_user)

        self.client.force_authenticate(user=another_user)
        resp = self.client.get(
            self.get_detail_url(instance.tex_key))
        self.assertEqual(resp.status_code, 200)

        self.client.force_authenticate(user=self.test_user)
        resp = self.client.get(
            self.get_detail_url(instance.tex_key))
        self.assertEqual(resp.status_code, 404)

        self.client.force_authenticate(user=self.superuser)
        resp = self.client.get(
            self.get_detail_url(instance.tex_key))
        self.assertEqual(resp.status_code, 200)

    def test_get_success(self):
        instance = factories.LatexImageFactory(creator=self.test_user)

        resp = self.client.get(
            self.get_detail_url(instance.tex_key))
        self.assertEqual(resp.status_code, 200)

    def test_get_success_filter_fields(self):
        instance = factories.LatexImageFactory(creator=self.test_user)

        filter_fields = ["data_url", "creator"]

        resp = self.client.get(
            self.get_detail_url(instance.tex_key, fields=filter_fields))
        self.assertEqual(resp.status_code, 200)
        response_dict = json.loads(resp.content.decode())
        self.assertEqual(
            sorted(filter_fields), sorted(list(response_dict.keys())))

    def test_put_success(self):
        first_instance = self.create_n_instances(n=1)[0]
        first_instance_size = first_instance.image.size
        first_instance_path = first_instance.image.path

        self.client.post(
            self.get_list_url(),
            data=self.get_post_data(),
            format='json')

        second_instance = LatexImage.objects.last()
        second_data_url = second_instance.data_url
        second_instance_size = second_instance.image.size
        second_instance.delete()

        self.assertEqual(LatexImage.objects.all().count(), 1)

        resp = self.client.put(
            self.get_detail_url(first_instance.tex_key),
            data={
                "tex_key": first_instance.tex_key,
                "data_url": second_data_url,
                "creator": self.test_user.pk,
            }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(LatexImage.objects.all().count(), 1)

        # The image is overwrote
        self.assertEqual(first_instance_path, LatexImage.objects.first().image.path)
        self.assertEqual(LatexImage.objects.first().data_url, second_data_url)
        self.assertEqual(LatexImage.objects.first().image.size, second_instance_size)
        self.assertNotEqual(LatexImage.objects.first().image.size, first_instance_size)

    def test_patch_success(self):
        first_instance = self.create_n_instances(n=1)[0]
        first_instance_size = first_instance.image.size
        first_instance_path = first_instance.image.path

        self.client.post(
            self.get_list_url(),
            data=self.get_post_data(),
            format='json')

        second_instance = LatexImage.objects.last()
        second_data_url = second_instance.data_url
        second_instance_size = second_instance.image.size
        second_instance.delete()

        self.assertEqual(LatexImage.objects.all().count(), 1)

        resp = self.client.patch(
            self.get_detail_url(first_instance.tex_key),
            data={
                "data_url": second_data_url,
            }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(LatexImage.objects.all().count(), 1)

        # The image is overwrote
        self.assertEqual(first_instance_path, LatexImage.objects.first().image.path)
        self.assertEqual(LatexImage.objects.first().data_url, second_data_url)
        self.assertEqual(LatexImage.objects.first().image.size, second_instance_size)
        self.assertNotEqual(LatexImage.objects.first().image.size, first_instance_size)


class LatexCreateAPITest(APITestBaseMixin, TestCase):
    def test_create_success_svg(self):
        resp = self.client.post(
            self.get_list_url(),
            data=self.get_post_data(
                file_dir="latex2svg", image_format="svg",
                compiler="latex"
            ),
            format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(LatexImage.objects.all().count(), 1)
        self.assertIsNotNone(LatexImage.objects.first().image.url)

    def test_no_create_success(self):
        first_instance = self.create_n_instances()[0]

        resp = self.client.post(
            self.get_creat_url(),
            data=self.get_post_data(tex_key=first_instance.tex_key),
            format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(LatexImage.objects.all().count(), self.n_new)

    def test_create_success(self):
        self.create_n_instances()

        resp = self.client.post(
            self.get_creat_url(),
            data=self.get_post_data(tex_key="whatever"),
            format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(LatexImage.objects.all().count(), self.n_new + 1)

    @suppress_stdout_decorator(suppress_stderr=True)
    def test_post_data_error_not_compile_error(self):
        post_data = self.get_post_data()
        del post_data["tex_source"]

        resp = self.client.post(
            self.get_creat_url(), data=post_data, format='json')
        self.assertContains(resp, "KeyError", status_code=500)
        self.assertEqual(LatexImage.objects.all().count(), 0)

    def test_create_success_filter_fields(self):
        filter_fields_str = "data_url,creation_time"

        resp = self.client.post(
            self.get_creat_url(),
            data=self.get_post_data(tex_key="whatever", fields=filter_fields_str),
            format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(LatexImage.objects.all().count(), 1)
        response_dict = json.loads(resp.content.decode())
        self.assertEqual(
            sorted(filter_fields_str.split(",")),
            sorted(list(response_dict.keys())))


class CacheTestBase(APITestBaseMixin):
    def setUp(self):
        super().setUp()
        tex_key = "what_ever_key"
        self._obj = factories.LatexImageFactory(
            tex_key=tex_key, creator=self.test_user)
        self.assertEqual(LatexImage.objects.all().count(), 1)
        self.tex_key = tex_key

        # Here we assume all caches are lost for some reason
        self.test_cache.clear()

    def get_field_cache_key(self, field_name, tex_key=None):
        tex_key = tex_key or self.tex_key
        return "%s:%s" % (tex_key, field_name)

    def set_field_cache(self, field_name, value=None, tex_key=None):
        cache_key = self.get_field_cache_key(field_name, tex_key)
        value = value or getattr(self._obj, field_name)
        self.test_cache.add(cache_key, value)

    @improperly_configured_cache_patch()
    def test_disable_cache(self, mock_cache):
        from django.core.exceptions import ImproperlyConfigured
        with self.assertRaises(ImproperlyConfigured):
            from django.core.cache import cache  # noqa


class DetailViewCacheTest(CacheTestBase, TestCase):
    def test_get_cached_image_arbitrary_value(self):
        filter_fields_str = "image"
        cache_key = self.get_field_cache_key(filter_fields_str)

        arbitrary_cache_value = "bar"
        self.set_field_cache(filter_fields_str, value=arbitrary_cache_value)

        with mock.patch(
                "rest_framework.generics.RetrieveUpdateDestroyAPIView.get"
        ) as mock_api_get:
            resp = self.client.get(
                self.get_detail_url(
                    self.tex_key, fields=filter_fields_str))
            mock_api_get.assert_not_called()

            self.assertEqual(
                self.test_cache.get(cache_key), arbitrary_cache_value)

            response_dict = json.loads(resp.content.decode())
            self.assertIn("image", response_dict)
            self.assertEqual(
                response_dict["image"], arbitrary_cache_value)

    def test_get_cached_dataurl(self):
        filter_fields_str = "data_url"
        self.set_field_cache(filter_fields_str)
        with mock.patch(
                "rest_framework.generics.RetrieveUpdateDestroyAPIView.get"
        ) as mock_api_get:
            resp = self.client.get(
                self.get_detail_url(
                    self.tex_key, fields=filter_fields_str))
            mock_api_get.assert_not_called()
            response_dict = json.loads(resp.content.decode())
            self.assertIn("data_url", response_dict)
            self.assertTrue(
                response_dict["data_url"].startswith("data"),
                response_dict["data_url"])

    def test_get_cached_result_success_dataurl_not_in_cache(self):
        filter_fields_str = "data_url"

        with mock.patch(
                "rest_framework.generics.RetrieveUpdateDestroyAPIView.get"
        ) as mock_api_get:
            resp = self.client.get(
                self.get_detail_url(
                    self.tex_key, fields=filter_fields_str))
            mock_api_get.assert_not_called()
            response_dict = json.loads(resp.content.decode())
            self.assertIn("data_url", response_dict)
            self.assertTrue(
                response_dict["data_url"].startswith("data"),
                response_dict["data_url"])

        self.assertEqual(
            self.test_cache.get(self.get_field_cache_key(filter_fields_str)),
            self._obj.data_url)

    def test_get_cached_result_of_none_exist_obj(self):
        filter_fields_str = "image"

        tex_key = "nono_exist_key"

        cache_key = self.get_field_cache_key(
            filter_fields_str, tex_key=tex_key)

        with mock.patch(
                "rest_framework.generics.RetrieveUpdateDestroyAPIView.get"
        ) as mock_api_get:
            resp = self.client.get(
                self.get_detail_url(
                    tex_key=tex_key, fields=filter_fields_str))
            mock_api_get.assert_not_called()
            response_dict = json.loads(resp.content.decode())
            self.assertTrue(len(response_dict.keys()) == 0)

        self.assertIsNone(self.test_cache.get(cache_key))

    def test_get_cached_result_of_none_exist_attribute_name(self):
        filter_fields_str = "none_exist"

        cache_key = self.get_field_cache_key(filter_fields_str)

        with mock.patch(
                "rest_framework.generics.RetrieveUpdateDestroyAPIView.get"
        ) as mock_api_get:
            resp = self.client.get(
                self.get_detail_url(
                    tex_key=self.tex_key, fields=filter_fields_str))
            mock_api_get.assert_not_called()
            response_dict = json.loads(resp.content.decode())
            self.assertTrue(len(response_dict.keys()) == 0)

        self.assertIsNone(self.test_cache.get(cache_key))

    def test_get_with_compile_error_in_cache(self):
        tex_key = "what_ever_error_key"
        instance = factories.LatexImageErrorFactory(
            tex_key=tex_key, creator=self.test_user)

        filter_fields_str = "image"

        with mock.patch(
                "rest_framework.generics.RetrieveUpdateDestroyAPIView.get"
        ) as mock_api_get:
            resp = self.client.get(
                self.get_detail_url(
                    tex_key=tex_key, fields=filter_fields_str),
                format='json')
            mock_api_get.assert_not_called()

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(LatexImage.objects.all().count(), 2)
        response_dict = json.loads(resp.content.decode())
        self.assertNotIn(filter_fields_str, response_dict)
        self.assertIn("compile_error", response_dict)
        self.assertEqual(
            response_dict["compile_error"], instance.compile_error)

    def test_get_cached_result_with_compile_error_not_in_cache(self):
        tex_key = "what_ever_error_key"
        instance = factories.LatexImageErrorFactory(
            tex_key=tex_key, creator=self.test_user)

        self.test_cache.clear()

        filter_fields_str = "image"

        with mock.patch(
                "rest_framework.generics.RetrieveUpdateDestroyAPIView.get"
        ) as mock_api_get:
            resp = self.client.get(
                self.get_detail_url(
                    tex_key=tex_key, fields=filter_fields_str),
                format='json')
            mock_api_get.assert_not_called()

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(LatexImage.objects.all().count(), 2)
        response_dict = json.loads(resp.content.decode())
        self.assertNotIn(filter_fields_str, response_dict)
        self.assertIn("compile_error", response_dict)
        self.assertEqual(
            response_dict["compile_error"], instance.compile_error)

        cache_key = self.get_field_cache_key("compile_error", tex_key=tex_key)

        # Compile error get cached.
        self.assertEqual(
            self.test_cache.get(cache_key), instance.compile_error)

    @override_settings(L2I_CACHE_MAX_BYTES=1)
    def test_result_not_cached_size_exceed(self):
        filter_fields_str = "data_url"

        with mock.patch(
                "rest_framework.generics.RetrieveUpdateDestroyAPIView.get"
        ) as mock_api_get:
            resp = self.client.get(
                self.get_detail_url(
                    self.tex_key, fields=filter_fields_str))
            mock_api_get.assert_not_called()
            response_dict = json.loads(resp.content.decode())
            self.assertIn("data_url", response_dict)
            self.assertTrue(
                response_dict["data_url"].startswith("data"),
                response_dict["data_url"])

        # result not cached
        self.assertIsNone(
            self.test_cache.get(
                self.get_field_cache_key(filter_fields_str)))

    @override_settings(L2I_API_IMAGE_RETURNS_RELATIVE_PATH=False)
    def test_L2I_API_IMAGE_RETURNS_RELATIVE_PATH_false_no_http_media_url(self):
        # The query to image will return image url
        filter_fields_str = "image"

        media_url = "http://testserver/my_media/"
        with override_settings(MEDIA_URL="/my_media/"):
            resp = self.client.get(
                self.get_detail_url(
                    self.tex_key, fields=filter_fields_str))
            response_dict = json.loads(resp.content.decode())
            self.assertIn("image", response_dict)
            self.assertTrue(
                response_dict["image"].startswith(media_url))

    @override_settings(L2I_API_IMAGE_RETURNS_RELATIVE_PATH=False)
    def test_L2I_API_IMAGE_RETURNS_RELATIVE_PATH_false_with_http_media_url(self):
        # The query to image will return image url
        filter_fields_str = "image"

        media_url = "http://my_example_testserver.com/my_media/"
        with override_settings(MEDIA_URL=media_url):
            resp = self.client.get(
                self.get_detail_url(
                    self.tex_key, fields=filter_fields_str))
            response_dict = json.loads(resp.content.decode())
            self.assertIn("image", response_dict)
            self.assertTrue(
                response_dict["image"].startswith(media_url))

    def test_get_result_with_obj_exist_compile_error_no_cache(self):
        tex_key = "what_ever_error_key"
        filter_fields_str = "image"

        with improperly_configured_cache_patch():
            instance = factories.LatexImageErrorFactory(
                tex_key=tex_key, creator=self.test_user)

            resp = self.client.get(
                self.get_detail_url(
                    tex_key=instance.tex_key, fields=filter_fields_str),
                format='json')

        with improperly_configured_cache_patch():
            self.assertEqual(resp.status_code, 400)
            self.assertEqual(LatexImage.objects.all().count(), 2)


class CreateViewCacheTest(CacheTestBase, TestCase):
    def test_post_create_data_url_not_cached_get_cached(self):
        filter_fields_str = "data_url"
        cache_key = self.get_field_cache_key(filter_fields_str)

        resp = self.client.post(
            self.get_creat_url(),
            data=self.get_post_data(
                tex_key=self.tex_key, fields=filter_fields_str),
            format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(LatexImage.objects.all().count(), 1)
        self.assertIsNotNone(self.test_cache.get(cache_key))
        self.assertEqual(self.test_cache.get(cache_key), self._obj.data_url)

        response_dict = json.loads(resp.content.decode())
        self.assertEqual(
            sorted(filter_fields_str.split(",")),
            sorted(list(response_dict.keys())))

    @override_settings(L2I_API_IMAGE_RETURNS_RELATIVE_PATH=True)
    def test_post_create_image_not_cached_get_cached_image_return_relative_path(self):
        filter_fields_str = "image"
        cache_key = self.get_field_cache_key(filter_fields_str)

        resp = self.client.post(
            self.get_creat_url(),
            data=self.get_post_data(
                tex_key=self.tex_key, fields=filter_fields_str),
            format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(LatexImage.objects.all().count(), 1)
        self.assertIsNotNone(self.test_cache.get(cache_key))
        self.assertEqual(
            self.test_cache.get(cache_key), str(self._obj.image))

        # The path should starts with IMAGE_PATH_PREFIX
        self.assertTrue(
            self.test_cache.get(cache_key).startswith(IMAGE_PATH_PREFIX))

    @override_settings(L2I_API_IMAGE_RETURNS_RELATIVE_PATH=False)
    def test_post_create_image_not_cached_get_cached_image_return_url(self):
        filter_fields_str = "image"
        cache_key = self.get_field_cache_key(filter_fields_str)

        resp = self.client.post(
            self.get_creat_url(),
            data=self.get_post_data(
                tex_key=self.tex_key, fields=filter_fields_str),
            format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(LatexImage.objects.all().count(), 1)
        self.assertIsNotNone(self.test_cache.get(cache_key))

        # The path should starts with http
        self.assertTrue(
            self.test_cache.get(cache_key).startswith("http"))

    def test_post_create_field_obj_exist_cache_improperly_configured(self):
        filter_fields_str = "image"

        with improperly_configured_cache_patch():
            resp = self.client.post(
                self.get_creat_url(),
                data=self.get_post_data(
                    tex_key=self.tex_key, fields=filter_fields_str),
                format='json')
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(LatexImage.objects.all().count(), 1)
            response_dict = json.loads(resp.content.decode())
            self.assertEqual(
                sorted(filter_fields_str.split(",")),
                sorted(list(response_dict.keys())))
