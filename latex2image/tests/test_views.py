from __future__ import division

__copyright__ = "Copyright (C) 2017 Dong Zhuang"

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

import os
import json
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest import mock
from django.contrib.auth import get_user_model
from django.conf import settings
from rest_framework.authtoken.models import Token
from rest_framework.test import (
    force_authenticate, APIRequestFactory, APIClient)

from tests import factories
from tests.base_test_mixins import (
    L2ITestMixinBase, get_latex_file_dir, suppress_stdout_decorator,
    get_fake_data_url
)

from latex.views import LatexImageList
from latex.models import LatexImage


class UerProfileTest(L2ITestMixinBase, TestCase):
    def test_non_auth_get(self):
        with self.temporarily_switch_to_user(None):
            resp = self.c.get(self.get_profile_view_url())
        self.assertTrue(resp.status_code, 400)

    def test_auth_get(self):
        with self.temporarily_switch_to_user(self.test_user):
            resp = self.c.get(self.get_profile_view_url())
        self.assertTrue(resp.status_code, 200)

    def test_auth_post(self):
        data = self._user_create_kwargs.copy()
        data.pop("password")
        another_email = "another_email@example.com"
        data["email"] = another_email

        # No "submit" in post
        with self.temporarily_switch_to_user(self.test_user):
            resp = self.c.post(self.get_profile_view_url(), data=data)
        self.assertTrue(resp.status_code, 200)

        self.assertNotEqual(
            get_user_model().objects.get(username=self.test_user.username).email,
            another_email)

        # Update
        with self.temporarily_switch_to_user(self.test_user):
            resp = self.post_profile(data=data)
        self.assertTrue(resp.status_code, 200)

        self.assertEqual(
            get_user_model().objects.get(username=self.test_user.username).email,
            another_email)

        # Fail to update
        data["email"] = "not an email"
        with self.temporarily_switch_to_user(self.test_user):
            resp = self.post_profile(data=data)
        self.assertTrue(resp.status_code, 200)

        self.assertEqual(
            get_user_model().objects.get(username=self.test_user.username).email,
            another_email)

    def test_render_without_token(self):
        temp_user = factories.UserFactory(
            username="abc", password="whatever")
        Token.objects.filter(user=temp_user).delete()

        with self.temporarily_switch_to_user(temp_user):
            resp = self.c.get(self.get_profile_view_url())
        self.assertTrue(resp.status_code, 200)


class GetDataUrlFromLatexForm(L2ITestMixinBase, TestCase):
    def setUp(self):
        super(GetDataUrlFromLatexForm, self).setUp()
        self.c.force_login(self.test_user)
        assert LatexImage.objects.all().count() == 0

    @staticmethod
    def get_post_data(file_dir="xelatex", **kwargs):
        doc_path = get_latex_file_dir(file_dir)
        file_path = os.path.join(
            doc_path, os.listdir(doc_path)[0])

        with open(file_path, encoding="utf-8") as f:
            file_data = f.read().encode()

        uploaded_file = SimpleUploadedFile(
            "xelatex.tex", file_data, content_type="text/plain")
        data = {
            "compiler_format": "xelatex2png",
            "latex_file": uploaded_file, "tex_key": ""}
        data.update(kwargs)
        return data

    def test_non_auth_get(self):
        with self.temporarily_switch_to_user(None):
            resp = self.get_latex_form_view()
        self.assertTrue(resp.status_code, 302)

    def test_non_auth_post(self):
        with mock.patch(
                "latex.converter.Tex2ImgBase.get_converted_data_url"
        ) as mock_convert:
            mock_convert.return_value = get_fake_data_url("foob=")
            with self.temporarily_switch_to_user(None):
                resp = self.post_latex_form_view(
                    data=self.get_post_data())
            self.assertTrue(resp.status_code, 302)
            self.assertEqual(LatexImage.objects.all().count(), 0)
            self.assertEqual(mock_convert.call_count, 0)

    def test_auth_get(self):
        resp = self.get_latex_form_view()
        self.assertTrue(resp.status_code, 200)

    def test_pos_form_invalid(self):
        form_data = self.get_post_data()
        del form_data["latex_file"]
        resp = self.post_latex_form_view(data=form_data)
        self.assertTrue(resp.status_code, 200)
        self.assertFormError(
            resp, form="form", field="latex_file",
            errors=["This field is required."])
        self.assertResponseContextIsNone(resp, "data_url")
        self.assertResponseContextIsNone(resp, "error")
        self.assertEqual(LatexImage.objects.all().count(), 0)

    def test_post_success(self):
        resp = self.post_latex_form_view(data=self.get_post_data())

        self.assertTrue(resp.status_code, 200)
        self.assertResponseContextIsNotNone(resp, "data_url")
        self.assertResponseContextIsNone(resp, "error")
        self.assertEqual(LatexImage.objects.all().count(), 1)

    def test_post_success_multiple_user_same_data(self):
        self.post_latex_form_view(data=self.get_post_data())

        with self.temporarily_switch_to_user(self.superuser):
            resp = self.post_latex_form_view(data=self.get_post_data())
            self.assertTrue(resp.status_code, 200)
            self.assertResponseContextIsNotNone(resp, "data_url")
            self.assertResponseContextIsNone(resp, "error")
            self.assertEqual(LatexImage.objects.all().count(), 1)

    def test_post_success_no_convert_if_exist(self):
        self.post_latex_form_view(data=self.get_post_data())
        self.assertEqual(LatexImage.objects.all().count(), 1)

        with mock.patch(
                "latex.converter.Tex2ImgBase.get_converted_data_url"
        ) as mock_convert:
            mock_convert.return_value = get_fake_data_url("foob=")
            resp = self.post_latex_form_view(
                data=self.get_post_data())
            self.assertEqual(mock_convert.call_count, 0)

        self.assertTrue(resp.status_code, 200)
        self.assertResponseContextIsNotNone(resp, "data_url")
        self.assertResponseContextIsNone(resp, "error")
        self.assertEqual(LatexImage.objects.all().count(), 1)

    def test_post_success_no_convert_if_exist_but_with_tex_key(self):
        self.post_latex_form_view(data=self.get_post_data())
        self.assertEqual(LatexImage.objects.all().count(), 1)

        tex_key = "__abcd"

        with mock.patch(
                "latex.converter.Tex2ImgBase.get_converted_data_url"
        ) as mock_convert:
            mock_convert.return_value = get_fake_data_url("foob=")
            resp = self.post_latex_form_view(
                data=self.get_post_data(tex_key=tex_key))
            self.assertEqual(mock_convert.call_count, 1)

        self.assertTrue(resp.status_code, 200)
        self.assertResponseContextIsNotNone(resp, "data_url")
        self.assertResponseContextIsNone(resp, "error")
        self.assertEqual(LatexImage.objects.all().count(), 2)

    def test_post_success_no_convert_if_exist_with_tex_key(self):
        tex_key = "what_ever_key"
        _obj = factories.LatexImageFactory(tex_key=tex_key)
        self.assertEqual(LatexImage.objects.all().count(), 1)

        with mock.patch(
                "latex.converter.Tex2ImgBase.get_converted_data_url"
        ) as mock_convert:
            mock_convert.return_value = get_fake_data_url("foob=")
            resp = self.post_latex_form_view(
                data=self.get_post_data(tex_key=tex_key))
            self.assertEqual(mock_convert.call_count, 0)

        self.assertTrue(resp.status_code, 200)
        self.assertResponseContextIsNotNone(resp, "data_url")
        self.assertResponseContextIsNone(resp, "error")
        self.assertEqual(LatexImage.objects.all().count(), 1)
        self.assertEqual(LatexImage.objects.all()[0].data_url, _obj.data_url)

    # noinspection DuplicatedCode
    @suppress_stdout_decorator(suppress_stderr=True)
    def test_post_errored(self):
        resp = self.post_latex_form_view(
            data=self.get_post_data(file_dir="lualatex"))

        self.assertTrue(resp.status_code, 200)
        self.assertResponseContextIsNone(resp, "data_url")
        self.assertResponseContextIsNotNone(resp, "error")
        self.assertEqual(LatexImage.objects.all().count(), 1)

    # noinspection DuplicatedCode
    @suppress_stdout_decorator(suppress_stderr=True)
    def test_post_errored_no_convert_if_exist(self):
        self.post_latex_form_view(
            data=self.get_post_data(file_dir="lualatex"))

        self.assertEqual(LatexImage.objects.all().count(), 1)

        with mock.patch(
                "latex.converter.Tex2ImgBase.get_converted_data_url") as mock_convert:
            mock_convert.return_value = get_fake_data_url("foob=")
            resp = self.post_latex_form_view(
                data=self.get_post_data(file_dir="lualatex"))

            self.assertTrue(resp.status_code, 200)
            self.assertResponseContextIsNone(resp, "data_url")
            self.assertResponseContextIsNotNone(resp, "error")
            self.assertEqual(LatexImage.objects.all().count(), 1)
            self.assertEqual(mock_convert.call_count, 0)

    # noinspection DuplicatedCode
    @suppress_stdout_decorator(suppress_stderr=True)
    def test_post_errored_no_convert_if_exist_with_tex_key(self):
        tex_key = "what_ever_key_error"
        factories.LatexImageErrorFactory(tex_key=tex_key)
        self.assertEqual(LatexImage.objects.all().count(), 1)

        with mock.patch(
                "latex.converter.Tex2ImgBase.get_converted_data_url"
        ) as mock_convert:
            mock_convert.return_value = get_fake_data_url("foob=")
            resp = self.post_latex_form_view(
                data=self.get_post_data(tex_key=tex_key))

            self.assertTrue(resp.status_code, 200)
            self.assertResponseContextIsNone(resp, "data_url")
            self.assertResponseContextIsNotNone(resp, "error")
            self.assertEqual(LatexImage.objects.all().count(), 1)
            self.assertEqual(mock_convert.call_count, 0)

    @suppress_stdout_decorator(suppress_stderr=True)
    def test_post_error_not_latex_compile_error(self):
        exception_str = "this is a custom exception."
        with mock.patch(
                "latex.converter.Tex2ImgBase.get_converted_data_url"
        ) as mock_convert:
            mock_convert.side_effect = RuntimeError(exception_str)
            resp = self.post_latex_form_view(data=self.get_post_data())

            self.assertTrue(resp.status_code, 200)
            self.assertResponseContextIsNone(resp, "data_url")
            self.assertResponseContextIsNotNone(resp, "error")
            self.assertEqual(LatexImage.objects.all().count(), 0)
            self.assertResponseContextContains(resp, "error", exception_str)


class LatexListTest(L2ITestMixinBase, TestCase):
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

    def test_get_not_authenticated(self):
        n_objects = 2
        factories.LatexImageFactory.create_batch(size=n_objects)

        client = APIClient()
        client.force_authenticate(user=None)
        resp = client.get(self.get_list_url())
        self.assertEqual(resp.status_code, 401)

    def test_get_success(self):
        n_objects = 2
        factories.LatexImageFactory.create_batch(
            size=n_objects, creator=self.test_user)

        view = LatexImageList.as_view()
        request = APIRequestFactory().get(self.get_list_url())
        force_authenticate(request, user=self.test_user)
        resp = view(request)
        resp.render()
        self.assertEqual(len(json.loads(resp.content.decode())), n_objects)
        self.assertEqual(resp.status_code, 200)

    def test_create_success(self):
        client = APIClient()
        client.force_authenticate(user=self.test_user)
        resp = client.post(
            self.get_list_url(), data=self.get_post_data(), format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(LatexImage.objects.all().count(), 1)
        self.assertIsNotNone(LatexImage.objects.first().image.url)

    def test_create_success_svg(self):
        client = APIClient()
        client.force_authenticate(user=self.test_user)
        resp = client.post(
            self.get_list_url(),
            data=self.get_post_data(
                file_dir="latex2svg", image_format="svg",
                compiler="latex"
            ),
            format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(LatexImage.objects.all().count(), 1)
        self.assertIsNotNone(LatexImage.objects.first().image.url)

    def test_no_create_duplicate(self):
        tex_key = "what_ever_key"
        factories.LatexImageFactory(tex_key=tex_key, creator=self.test_user)

        client = APIClient()
        client.force_authenticate(user=self.test_user)

        with mock.patch(
                "latex.converter.Tex2ImgBase.get_converted_data_url") as mock_convert:
            mock_convert.return_value = get_fake_data_url("foob=")
            resp = client.post(
                self.get_list_url(),
                data=self.get_post_data(tex_key=tex_key), format='json')
            mock_convert.assert_not_called()

        self.assertEqual(resp.status_code, 201)
        self.assertEqual(LatexImage.objects.all().count(), 1)

    def test_no_create_duplicate_errored(self):
        tex_key = "what_ever_key"
        factories.LatexImageErrorFactory(tex_key=tex_key, creator=self.test_user)

        client = APIClient()
        client.force_authenticate(user=self.test_user)

        with mock.patch(
                "latex.converter.Tex2ImgBase.get_converted_data_url") as mock_convert:
            mock_convert.return_value = get_fake_data_url("foob=")
            resp = client.post(
                self.get_list_url(),
                data=self.get_post_data(tex_key=tex_key), format='json')
            mock_convert.assert_not_called()

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(LatexImage.objects.all().count(), 1)

    @suppress_stdout_decorator(suppress_stderr=True)
    def test_post_data_error_failure(self):
        client = APIClient()
        client.force_authenticate(user=self.test_user)

        post_data = self.get_post_data()
        del post_data["tex_source"]

        resp = client.post(
            self.get_list_url(), data=post_data, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(LatexImage.objects.all().count(), 0)

    @suppress_stdout_decorator(suppress_stderr=True)
    def test_converter_init_errored(self):
        client = APIClient()
        client.force_authenticate(user=self.test_user)

        resp = client.post(
            self.get_list_url(),
            data=self.get_post_data(compiler="latex", image_format="jpg"),
            format="json"
        )
        self.assertTrue(resp.status_code, 400)
        self.assertEqual(LatexImage.objects.all().count(), 0)

    @suppress_stdout_decorator(suppress_stderr=True)
    @mock.patch('django.core.files.storage.FileSystemStorage.save')
    def test_compile_errored(self, mock_save):
        client = APIClient()
        client.force_authenticate(user=self.test_user)

        resp = client.post(
            self.get_list_url(),
            data=self.get_post_data(
                file_dir="lualatex", compiler="latex", image_format="png"),
            format="json"
        )
        self.assertTrue(resp.status_code, 400)
        self.assertEqual(LatexImage.objects.all().count(), 1)
        # mock_save.assert_called_once()

    @suppress_stdout_decorator(suppress_stderr=True)
    @mock.patch('django.core.files.storage.FileSystemStorage.save')
    def test_not_compile_errored(self, mock_save):
        client = APIClient()
        client.force_authenticate(user=self.test_user)

        exception_str = "this is a custom exception."
        with mock.patch(
                "latex.converter.Tex2ImgBase.get_converted_data_url") as mock_convert:
            mock_convert.side_effect = RuntimeError(exception_str)
            resp = client.post(
                self.get_list_url(),
                data=self.get_post_data(),
                format="json"
            )
        self.assertTrue(resp.status_code, 400)
        self.assertEqual(LatexImage.objects.all().count(), 0)
        mock_save.assert_not_called()


class LatexDetailedTest(L2ITestMixinBase, TestCase):
    @staticmethod
    def get_post_data(**kwargs):
        xelatex_doc_path = get_latex_file_dir("xelatex")
        file_path = os.path.join(
            xelatex_doc_path, os.listdir(xelatex_doc_path)[0])

        with open(file_path, encoding="utf-8") as f:
            file_data = f.read()

        data = {
            "compiler": "xelatex",
            "tex_source": file_data,
            "image_format": "png",
        }
        data.update(kwargs)
        return data

    def test_get_not_authenticated(self):
        instance = factories.LatexImageFactory()

        client = APIClient()
        client.force_authenticate(user=None)
        resp = client.get(
            self.get_detail_url(instance.tex_key))
        self.assertEqual(resp.status_code, 401)

    def test_get_success(self):
        instance = factories.LatexImageFactory(creator=self.test_user)

        client = APIClient()
        client.force_authenticate(user=self.test_user)
        resp = client.get(
            self.get_detail_url(instance.tex_key))
        self.assertEqual(resp.status_code, 200)

    def test_get_success_filter_fields(self):
        instance = factories.LatexImageFactory(creator=self.test_user)

        client = APIClient()
        client.force_authenticate(user=self.test_user)

        filter_fields = ["data_url", "creator"]

        resp = client.get(
            self.get_detail_url(instance.tex_key, fields=filter_fields))
        self.assertEqual(resp.status_code, 200)
        response_dict = json.loads(resp.content.decode())
        self.assertEqual(
            sorted(filter_fields), sorted(list(response_dict.keys())))


class LatexCreateTest(L2ITestMixinBase, TestCase):
    @staticmethod
    def get_post_data(**kwargs):
        xelatex_doc_path = get_latex_file_dir("xelatex")
        file_path = os.path.join(
            xelatex_doc_path, os.listdir(xelatex_doc_path)[0])

        with open(file_path, encoding="utf-8") as f:
            file_data = f.read()

        data = {
            "compiler": "xelatex",
            "tex_source": file_data,
            "image_format": "png",
        }
        data.update(kwargs)
        return data

    def test_no_create_success(self):
        n_objects = 2
        factories.LatexImageFactory.create_batch(size=n_objects)

        first_instance = LatexImage.objects.first()

        client = APIClient()
        client.force_authenticate(user=self.test_user)
        resp = client.post(
            self.get_creat_url(),
            data=self.get_post_data(tex_key=first_instance.tex_key),
            format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(LatexImage.objects.all().count(), n_objects)

    def test_create_success(self):
        n_objects = 2
        factories.LatexImageFactory.create_batch(size=n_objects)

        client = APIClient()
        client.force_authenticate(user=self.test_user)
        resp = client.post(
            self.get_creat_url(),
            data=self.get_post_data(tex_key="whatever"),
            format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(LatexImage.objects.all().count(), n_objects + 1)

    def test_create_success_filter_fields(self):
        client = APIClient()
        client.force_authenticate(user=self.test_user)

        filter_fields_str = "data_url,creation_time"

        resp = client.post(
            self.get_creat_url(),
            data=self.get_post_data(tex_key="whatever", fields=filter_fields_str),
            format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(LatexImage.objects.all().count(), 1)
        response_dict = json.loads(resp.content.decode())
        self.assertEqual(
            sorted(filter_fields_str.split(",")),
            sorted(list(response_dict.keys())))


class Latex2ImageCacheTest(L2ITestMixinBase, TestCase):
    @staticmethod
    def get_post_data(**kwargs):
        xelatex_doc_path = get_latex_file_dir("xelatex")
        file_path = os.path.join(
            xelatex_doc_path, os.listdir(xelatex_doc_path)[0])

        with open(file_path, encoding="utf-8") as f:
            file_data = f.read()

        data = {
            "compiler": "xelatex",
            "tex_source": file_data,
            "image_format": "png",
        }
        data.update(kwargs)
        return data

    @override_settings(L2I_API_CACHE_FIELD="image")
    def test_post_cached_result_None(self):
        tex_key = "what_ever_key"
        _obj = factories.LatexImageFactory(
            tex_key=tex_key, creator=self.test_user)
        self.assertEqual(LatexImage.objects.all().count(), 1)

        client = APIClient()
        client.force_authenticate(user=self.test_user)

        # Because L2I_API_CACHE_FIELD != "data_url
        filter_fields_str = "data_url"

        resp = client.post(
            self.get_creat_url(),
            data=self.get_post_data(
                tex_key=tex_key, fields=filter_fields_str),
            format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(LatexImage.objects.all().count(), 1)
        self.assertIsNone(self.test_cache.get(tex_key))

    @override_settings(L2I_API_CACHE_FIELD="image")
    def test_post_cached_result_success(self):
        tex_key = "what_ever_key"
        _obj = factories.LatexImageFactory(
            tex_key=tex_key, creator=self.test_user)
        self.assertEqual(LatexImage.objects.all().count(), 1)

        client = APIClient()
        client.force_authenticate(user=self.test_user)

        filter_fields_str = "image"

        resp = client.post(
            self.get_creat_url(),
            data=self.get_post_data(
                tex_key=tex_key, fields=filter_fields_str),
            format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(LatexImage.objects.all().count(), 1)
        self.assertIsNotNone(self.test_cache.get(tex_key))

    @override_settings(L2I_API_CACHE_FIELD="image")
    def test_get_cached_result_success(self):
        instance = factories.LatexImageFactory()

        client = APIClient()
        client.force_authenticate(user=None)
        resp = client.get(
            self.get_detail_url(instance.tex_key))
        self.assertEqual(resp.status_code, 401)

        self.test_cache.add(instance.tex_key, str(instance.image))

        client = APIClient()
        client.force_authenticate(user=self.test_user)

        filter_fields_str = "image"

        with mock.patch(
                "rest_framework.generics.RetrieveUpdateDestroyAPIView.get"
        ) as mock_api_get:
            resp = client.get(
                self.get_detail_url(
                    instance.tex_key, fields=filter_fields_str))
            mock_api_get.assert_not_called()
            response_dict = json.loads(resp.content.decode())
            self.assertIn("image", response_dict)
            self.assertTrue(response_dict["image"].startswith("http"))

    @override_settings(L2I_API_CACHE_FIELD="data_url")
    def test_get_cached_result_success_dataurl_cached(self):
        instance = factories.LatexImageFactory()

        client = APIClient()
        client.force_authenticate(user=None)
        resp = client.get(
            self.get_detail_url(instance.tex_key))
        self.assertEqual(resp.status_code, 401)

        self.test_cache.add(instance.tex_key, str(instance.data_url))

        client = APIClient()
        client.force_authenticate(user=self.test_user)

        filter_fields_str = "data_url"

        with mock.patch(
                "rest_framework.generics.RetrieveUpdateDestroyAPIView.get"
        ) as mock_api_get:
            resp = client.get(
                self.get_detail_url(
                    instance.tex_key, fields=filter_fields_str))
            mock_api_get.assert_not_called()
            response_dict = json.loads(resp.content.decode())
            self.assertIn("data_url", response_dict)
            self.assertTrue(
                response_dict["data_url"].startswith("data"),
                response_dict["data_url"])

    @override_settings(L2I_API_CACHE_FIELD="data_url")
    def test_get_cached_result_success_dataurl_not_in_cache(self):
        instance = factories.LatexImageFactory()

        client = APIClient()
        client.force_authenticate(user=None)
        resp = client.get(
            self.get_detail_url(instance.tex_key))
        self.assertEqual(resp.status_code, 401)

        client = APIClient()
        client.force_authenticate(user=self.test_user)

        filter_fields_str = "data_url"

        with mock.patch(
                "rest_framework.generics.RetrieveUpdateDestroyAPIView.get"
        ) as mock_api_get:
            resp = client.get(
                self.get_detail_url(
                    instance.tex_key, fields=filter_fields_str))
            mock_api_get.assert_not_called()
            response_dict = json.loads(resp.content.decode())
            self.assertIn("data_url", response_dict)
            self.assertTrue(
                response_dict["data_url"].startswith("data"),
                response_dict["data_url"])

        self.assertEqual(
            self.test_cache.get(instance.tex_key),
            instance.data_url)

    @override_settings(L2I_API_CACHE_FIELD="image")
    def test_get_cached_result_success_not_exist(self):
        client = APIClient()
        client.force_authenticate(user=self.test_user)

        filter_fields_str = "image"

        with mock.patch(
                "rest_framework.generics.RetrieveUpdateDestroyAPIView.get"
        ) as mock_api_get:
            resp = client.get(
                self.get_detail_url(
                    tex_key="nono_exist_key", fields=filter_fields_str))
            mock_api_get.assert_not_called()
            response_dict = json.loads(resp.content.decode())
            self.assertTrue(len(response_dict.keys()) == 0)

    @override_settings(L2I_API_CACHE_FIELD="image")
    def test_get_cached_result_with_compile_error_in_cache(self):
        tex_key = "what_ever_key"
        instance = factories.LatexImageErrorFactory(
            tex_key=tex_key, creator=self.test_user)

        self.test_cache.add(
            tex_key + "_error", instance.compile_error)

        client = APIClient()
        client.force_authenticate(user=self.test_user)

        filter_fields_str = "image"

        with mock.patch(
                "rest_framework.generics.RetrieveUpdateDestroyAPIView.get"
        ) as mock_api_get:
            resp = client.get(
                self.get_detail_url(
                    tex_key=tex_key, fields=filter_fields_str),
                format='json')
            mock_api_get.assert_not_called()

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(LatexImage.objects.all().count(), 1)
        response_dict = json.loads(resp.content.decode())
        self.assertIn("compile_error", response_dict)
        self.assertEqual(
            response_dict["compile_error"], instance.compile_error)

    @override_settings(L2I_API_CACHE_FIELD="image")
    def test_get_cached_result_with_compile_error_not_in_cache(self):
        tex_key = "what_ever_key"
        instance = factories.LatexImageErrorFactory(
            tex_key=tex_key, creator=self.test_user)

        client = APIClient()
        client.force_authenticate(user=self.test_user)

        filter_fields_str = "image"

        with mock.patch(
                "rest_framework.generics.RetrieveUpdateDestroyAPIView.get"
        ) as mock_api_get:
            resp = client.get(
                self.get_detail_url(
                    tex_key=tex_key, fields=filter_fields_str),
                format='json')
            mock_api_get.assert_not_called()

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(LatexImage.objects.all().count(), 1)
        response_dict = json.loads(resp.content.decode())
        self.assertIn("compile_error", response_dict)
        self.assertEqual(
            response_dict["compile_error"], instance.compile_error)

        self.assertEqual(
            self.test_cache.get(tex_key + "_error"),
            instance.compile_error)

    @override_settings(
        L2I_API_CACHE_FIELD="data_url", L2I_CACHE_MAX_BYTES=1)
    def test_result_not_cached_size_exceed(self):
        instance = factories.LatexImageFactory()

        client = APIClient()
        client.force_authenticate(user=None)
        resp = client.get(
            self.get_detail_url(instance.tex_key))
        self.assertEqual(resp.status_code, 401)

        client = APIClient()
        client.force_authenticate(user=self.test_user)

        filter_fields_str = "data_url"

        with mock.patch(
                "rest_framework.generics.RetrieveUpdateDestroyAPIView.get"
        ) as mock_api_get:
            resp = client.get(
                self.get_detail_url(
                    instance.tex_key, fields=filter_fields_str))
            mock_api_get.assert_not_called()
            response_dict = json.loads(resp.content.decode())
            self.assertIn("data_url", response_dict)
            self.assertTrue(
                response_dict["data_url"].startswith("data"),
                response_dict["data_url"])

        self.assertIsNone(self.test_cache.get(instance.tex_key))

    @override_settings(L2I_API_CACHE_FIELD="image")
    def test_cached_image_url_change_with_media_url(self):
        # Make sure image url reflect change of settings.MEDIA_URL
        instance = factories.LatexImageFactory()
        self.test_cache.add(instance.tex_key, str(instance.image))

        client = APIClient()
        client.force_authenticate(user=self.test_user)
        filter_fields_str = "image"

        expected_url_prefix = "http://testserver/media/"
        with override_settings(MEDIA_URL="/media/"):
            resp = client.get(
                self.get_detail_url(
                    instance.tex_key, fields=filter_fields_str))
            response_dict = json.loads(resp.content.decode())
            self.assertIn("image", response_dict)
            self.assertTrue(
                response_dict["image"].startswith(expected_url_prefix))

        main_part = response_dict["image"][len(expected_url_prefix):]

        expected_url_prefix = "https://s3.example.com/my_images/"
        with override_settings(MEDIA_URL=expected_url_prefix):
            resp = client.get(
                self.get_detail_url(
                    instance.tex_key, fields=filter_fields_str))
            response_dict = json.loads(resp.content.decode())
            self.assertIn("image", response_dict)
            self.assertTrue(
                response_dict["image"].startswith(expected_url_prefix))
            self.assertEqual(
                response_dict["image"][len(expected_url_prefix):],
                main_part)
