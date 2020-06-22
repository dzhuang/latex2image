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


from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework.authtoken.models import Token

from tests import factories
from tests.base_test_mixins import L2ITestMixinBase


class LoginFormTest(L2ITestMixinBase, TestCase):
    def test_login_form_anonymous(self):
        with self.temporarily_switch_to_user(None):
            resp = self.c.get(self.get_login_view_url())
            self.assertEqual(resp.status_code, 200)

    def test_login_form(self):
        resp = self.c.get(self.get_login_view_url())
        self.assertEqual(resp.status_code, 200)


class UerProfileTest(L2ITestMixinBase, TestCase):
    def test_non_auth_get(self):
        with self.temporarily_switch_to_user(None):
            resp = self.c.get(self.get_profile_view_url())
        self.assertEqual(resp.status_code, 302)
        expected_redirect_url = (
            self.concatenate_redirect_url(
                reverse("login"), reverse("profile")))
        self.assertRedirects(resp, expected_redirect_url,
                             fetch_redirect_response=False)

    def test_auth_get(self):
        with self.temporarily_switch_to_user(self.test_user):
            resp = self.c.get(self.get_profile_view_url())
        self.assertEqual(resp.status_code, 200)

    def test_auth_post(self):
        data = self._user_create_kwargs.copy()
        data.pop("password")
        another_email = "another_email@example.com"
        data["email"] = another_email

        # No "submit" in post
        with self.temporarily_switch_to_user(self.test_user):
            resp = self.c.post(self.get_profile_view_url(), data=data)
        self.assertEqual(resp.status_code, 200)

        self.assertNotEqual(
            get_user_model().objects.get(username=self.test_user.username).email,
            another_email)

        # Update
        with self.temporarily_switch_to_user(self.test_user):
            resp = self.post_profile(data=data)
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(
            get_user_model().objects.get(username=self.test_user.username).email,
            another_email)

        # Fail to update
        data["email"] = "not an email"
        with self.temporarily_switch_to_user(self.test_user):
            resp = self.post_profile(data=data)
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(
            get_user_model().objects.get(username=self.test_user.username).email,
            another_email)

    def test_render_without_token(self):
        temp_user = factories.UserFactory(
            username="abc", password="whatever")
        Token.objects.filter(user=temp_user).delete()

        with self.temporarily_switch_to_user(temp_user):
            resp = self.c.get(self.get_profile_view_url())
        self.assertEqual(resp.status_code, 200)