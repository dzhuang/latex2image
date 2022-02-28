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


import os
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from tests import factories
from tests.base_test_mixins import (L2ITestMixinBase, get_fake_data_url,
                                    get_latex_file_dir,
                                    suppress_stdout_decorator)

from latex.models import LatexImage


class FormViewTest(L2ITestMixinBase, TestCase):
    def setUp(self):
        super().setUp()
        self.c.force_login(self.test_user)
        assert LatexImage.objects.all().count() == 0

    @staticmethod
    def get_post_data(file_dir="xelatex", **kwargs):
        as_text_field = kwargs.pop("as_text_field", False)
        doc_path = get_latex_file_dir(file_dir)
        file_path = os.path.join(
            doc_path, os.listdir(doc_path)[0])

        with open(file_path, encoding="utf-8") as f:
            file_data = f.read()

        data = {
            "compiler_format": "xelatex2png",
            "tex_key": ""}

        if not as_text_field:
            data["latex_file"] = SimpleUploadedFile(
                "xelatex.tex", file_data.encode(), content_type="text/plain")
        else:
            data["latex_code"] = file_data
        data.update(kwargs)
        return data

    def test_non_auth_get(self):
        with self.temporarily_switch_to_user(None):
            resp = self.get_latex_form_view(follow=False)
        self.assertEqual(resp.status_code, 302)

    def test_non_auth_post(self):
        with mock.patch(
                "latex.converter.Tex2ImgBase.get_converted_data_url"
        ) as mock_convert:
            mock_convert.return_value = get_fake_data_url("foob=")
            with self.temporarily_switch_to_user(None):
                resp = self.post_latex_form_view(
                    data=self.get_post_data(), follow=False)
            self.assertEqual(resp.status_code, 302)
            self.assertEqual(LatexImage.objects.all().count(), 0)
            self.assertEqual(mock_convert.call_count, 0)

    def test_auth_get(self):
        resp = self.get_latex_form_view(follow=False)
        self.assertEqual(resp.status_code, 200)

    def test_pos_form_invalid(self):
        form_data = self.get_post_data()
        del form_data["latex_file"]
        resp = self.post_latex_form_view(data=form_data)
        self.assertEqual(resp.status_code, 200)
        self.assertFormErrorLoose(
            resp, errors="Either", form_name="form")
        self.assertEqual(LatexImage.objects.all().count(), 0)

    def test_post_success(self):
        resp = self.post_latex_form_view(data=self.get_post_data())

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(LatexImage.objects.all().count(), 1)

    def test_post_success_text(self):
        resp = self.post_latex_form_view(
            data=self.get_post_data(as_text_field=True))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(LatexImage.objects.all().count(), 1)

    def test_post_success_multiple_user_same_data(self):
        self.post_latex_form_view(data=self.get_post_data())

        with self.temporarily_switch_to_user(self.superuser):
            resp = self.post_latex_form_view(data=self.get_post_data())
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(LatexImage.objects.all().count(), 1)

    def test_post_accidentally_delete_image_file(self):
        self.post_latex_form_view(data=self.get_post_data())
        image = LatexImage.objects.first().image
        os.remove(image.path)

        resp = self.post_latex_form_view(data=self.get_post_data())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(LatexImage.objects.all().count(), 1)
        self.assertResponseContextIsNone(resp, "size")

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

        self.assertEqual(resp.status_code, 200)
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

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(LatexImage.objects.all().count(), 2)

    def test_post_different_code_no_convert_if_same_tex_key_exists(self):
        tex_key = "what_ever_key"
        _obj = factories.LatexImageFactory(tex_key=tex_key)
        self.assertEqual(LatexImage.objects.all().count(), 1)

        with mock.patch(
                "latex.converter.Tex2ImgBase.get_converted_data_url"
        ) as mock_convert:
            resp = self.post_latex_form_view(
                data=self.get_post_data(tex_key=tex_key))
            mock_convert.assert_not_called()

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(LatexImage.objects.all().count(), 1)
        self.assertEqual(LatexImage.objects.all()[0].data_url, _obj.data_url)

    # noinspection DuplicatedCode
    @suppress_stdout_decorator(suppress_stderr=True)
    def test_post_compile_errored(self):
        resp = self.post_latex_form_view(
            data=self.get_post_data(file_dir="lualatex"))

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(LatexImage.objects.all().count(), 1)

    # noinspection DuplicatedCode
    @suppress_stdout_decorator(suppress_stderr=True)
    def test_post_errored_no_convert_if_exist(self):
        self.post_latex_form_view(
            data=self.get_post_data(file_dir="lualatex"))
        self.assertEqual(LatexImage.objects.all().count(), 1)

        with mock.patch(
                "latex.converter.Tex2ImgBase.get_converted_data_url"
        ) as mock_convert:
            resp = self.post_latex_form_view(
                data=self.get_post_data(file_dir="lualatex"))
            mock_convert.assert_not_called()

            self.assertEqual(resp.status_code, 400)
            self.assertEqual(LatexImage.objects.all().count(), 1)

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

            self.assertEqual(resp.status_code, 400)
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

            self.assertEqual(resp.status_code, 500)
            self.assertResponseContextIsNotNone(resp, "unknown_error")
            self.assertEqual(LatexImage.objects.all().count(), 0)
            self.assertResponseContextContains(resp, "unknown_error", exception_str)
