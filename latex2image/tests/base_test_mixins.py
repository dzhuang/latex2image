import os

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
import tempfile
from functools import wraps
from io import StringIO
from urllib.parse import quote

from django.test import Client, override_settings
from django.core.files.storage import FileSystemStorage
from django.urls import reverse
from django.contrib.auth import get_user_model, REDIRECT_FIELD_NAME
from django.core.exceptions import ImproperlyConfigured

from unittest import mock


CREATE_SUPERUSER_KWARGS = {
    "username": "test_admin",
    "password": "test_admin",
    "email": "test_admin@example.com",
    "first_name": "Test",
    "last_name": "Admin"}


class ResponseContextMixin(object):
    """
    Response context refers to "the template Context instance that was used
    to render the template that produced the response content".
    Ref: https://docs.djangoproject.com/en/dev/topics/testing/tools/#django.test.Response.context  # noqa
    """
    def get_response_context_value_by_name(self, response, context_name):
        try:
            value = response.context[context_name]
        except KeyError:
            self.fail("%s does not exist in given response" % context_name)
        else:
            return value

    def assertResponseHasNoContext(self, response, context_name):  # noqa
        has_context = True
        try:
            response.context[context_name]
        except KeyError:
            has_context = False
        if has_context:
            self.fail("%s unexpectedly exist in given response" % context_name)

    def assertResponseContextIsNone(self, resp, context_name):  # noqa
        try:
            value = self.get_response_context_value_by_name(resp, context_name)
        except AssertionError:
            # the context item doesn't exist
            pass
        else:
            self.assertIsNone(value)

    def assertResponseContextIsNotNone(self, resp, context_name, msg=""):  # noqa
        value = self.get_response_context_value_by_name(resp, context_name)
        self.assertIsNotNone(value, msg)

    def assertResponseContextEqual(self, resp, context_name, expected_value):  # noqa
        value = self.get_response_context_value_by_name(resp, context_name)
        try:
            self.assertTrue(float(value) - float(expected_value) <= 1e-04)
            return
        except Exception:
            self.assertEqual(value, expected_value)

    def assertResponseContextContains(self, resp,  # noqa
                                      context_name, expected_value, html=False,
                                      in_bulk=False):
        value = self.get_response_context_value_by_name(resp, context_name)
        if in_bulk:
            if not isinstance(expected_value, list):
                expected_value = [expected_value]

            for v in expected_value:
                if not html:
                    self.assertIn(v, value)
                else:
                    self.assertInHTML(v, value)
        else:
            if not html:
                self.assertIn(expected_value, value)
            else:
                self.assertInHTML(expected_value, value)

    def assertResponseContextRegex(  # noqa
            self, resp,  # noqa
            context_name, expected_value_regex):
        value = self.get_response_context_value_by_name(resp, context_name)
        self.assertRegex(value, expected_value_regex)

    def get_response_body(self, response):
        return self.get_response_context_value_by_name(response, "body")


class SuperuserCreateMixin(ResponseContextMixin):
    create_superuser_kwargs = CREATE_SUPERUSER_KWARGS

    @classmethod
    def setUpTestData(cls):  # noqa
        # Create superuser, without this, we cannot
        # create user, course and participation.
        cls.superuser = cls.create_superuser()
        cls.c = Client()
        cls.settings_git_root_override = (
            override_settings(GIT_ROOT=tempfile.mkdtemp()))
        cls.settings_git_root_override.enable()
        super().setUpTestData()

    @classmethod
    def create_superuser(cls):
        return get_user_model().objects.create_superuser(
            **cls.create_superuser_kwargs)

    @classmethod
    def get_login_view_url(cls):
        return reverse("login")

    @classmethod
    def get_sign_up_view_url(cls):
        return reverse("sign_up")

    @classmethod
    def get_sign_up(cls, follow=True):
        return cls.c.get(cls.get_sign_up_view_url(), follow=follow)

    @classmethod
    def post_sign_up(cls, data, follow=True):
        return cls.c.post(cls.get_sign_up_view_url(), data, follow=follow)

    @classmethod
    def get_profile_view_url(cls):
        return reverse("profile")

    @classmethod
    def get_latex_form_view_url(cls):
        return reverse("home")

    @classmethod
    def get_latex_form_view(cls, follow=True):
        return cls.c.get(cls.get_latex_form_view_url(), follow=follow)

    @classmethod
    def post_latex_form_view(cls, data, follow=True):
        return cls.c.post(cls.get_latex_form_view_url(), data=data, follow=follow)

    @classmethod
    def get_profile(cls, follow=True):
        return cls.c.get(cls.get_profile_view_url(), follow=follow)

    @classmethod
    def post_profile(cls, data, follow=True):
        data.update({"submit": [""]})
        return cls.c.post(cls.get_profile_view_url(), data, follow=follow)

    @classmethod
    def post_signout(cls, data, follow=True):
        return cls.c.post(cls.get_sign_up_view_url(), data, follow=follow)

    @classmethod
    def get_reset_password_url(cls):
        kwargs = {}
        return reverse("reset_password", kwargs=kwargs)

    @classmethod
    def get_list_url(cls, fields=None):
        url = reverse("list")
        if fields:
            url = url.rstrip("/") + "?fields=%s" % ",".join(fields)
        return url

    @classmethod
    def get_detail_url(cls, tex_key, fields=None):
        url = reverse("detail", args=(tex_key, ))
        if fields:
            if isinstance(fields, list):
                fields = ",".join(fields)
            else:
                assert isinstance(fields, str)
            url = url.rstrip("/") + "?fields=%s" % fields
        return url

    @classmethod
    def get_creat_url(cls, fields=None):
        url = reverse("create")
        if fields:
            url = url.rstrip("/") + "?fields=%s" % ",".join(fields)
        return url

    def assertFormErrorLoose(self, response, errors, form_name="form"):  # noqa
        """Assert that errors is found in response.context['form'] errors"""
        import itertools
        if errors is None:
            errors = []
        if not isinstance(errors, (list, tuple)):
            errors = [errors]
        try:
            form_errors = ". ".join(list(
                itertools.chain(*response.context[form_name].errors.values())))
        except TypeError:
            form_errors = None

        if form_errors is None or not form_errors:
            if errors:
                self.fail("%s has no error" % form_name)
            else:
                return

        if form_errors:
            if not errors:
                self.fail("%s unexpectedly has following errors: %s"
                          % (form_name, repr(form_errors)))

        for err in errors:
            self.assertIn(err, form_errors)

    @classmethod
    def concatenate_redirect_url(cls, url, redirect_to=None):
        if not redirect_to:
            return url
        return ('%(url)s?%(next)s=%(bad_url)s' % {
            'url': url,
            'next': REDIRECT_FIELD_NAME,
            'bad_url': quote(redirect_to),
        })


class L2ITestMixinBase(SuperuserCreateMixin):
    _user_create_kwargs = {
        "username": "test_user", "password": "mypassword",
        "email": "my_email@example.com"
    }

    def setUp(self):  # noqa
        temp_storage_dir = tempfile.mkdtemp(prefix="l2i_test_")

        # print(temp_storage_dir)

        # This is important. Don't destroy user data in tests.
        self.l2i_storage_settings_override = (
            override_settings(
                DEFAULT_FILE_STORAGE=FileSystemStorage(temp_storage_dir)))
        self.l2i_storage_settings_override.enable()
        self.addCleanup(self.l2i_storage_settings_override.disable)

        cache_override = override_settings(
            CACHES={
                'default': {
                    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'
                }
            }
        )

        cache_override.enable()

        import django.core.cache as cache
        self.test_cache = cache.caches["default"]

        self.addCleanup(self.test_cache.clear)
        self.addCleanup(cache_override.disable)

    @classmethod
    def setUpTestData(cls):  # noqa
        super().setUpTestData()
        cls.test_user = (
            get_user_model().objects.create_user(**cls._user_create_kwargs))
        cls.existing_user_count = get_user_model().objects.count()

    @classmethod
    def create_user(cls, create_user_kwargs):
        user, created = get_user_model().objects.get_or_create(
            email__iexact=create_user_kwargs["email"], defaults=create_user_kwargs)
        if created:
            try:
                # TODO: why pop failed here?
                password = create_user_kwargs["password"]
            except Exception:
                raise
            user.set_password(password)
            user.save()
        return user

    @classmethod
    def get_logged_in_user(cls):
        try:
            logged_in_user_id = cls.c.session['_auth_user_id']
            from django.contrib.auth import get_user_model
            logged_in_user = get_user_model().objects.get(
                pk=int(logged_in_user_id))
        except KeyError:
            logged_in_user = None
        return logged_in_user

    @classmethod
    def temporarily_switch_to_user(cls, switch_to):

        from functools import wraps

        class ClientUserSwitcher(object):
            def __init__(self, switch_to):
                self.client = cls.c
                self.switch_to = switch_to
                self.logged_in_user = cls.get_logged_in_user()

            def __enter__(self):
                if self.logged_in_user == self.switch_to:
                    return
                if self.switch_to is None:
                    self.client.logout()
                    return
                self.client.force_login(self.switch_to)

            def __exit__(self, exc_type, exc_val, exc_tb):
                if self.logged_in_user == self.switch_to:
                    return
                if self.logged_in_user is None:
                    self.client.logout()
                    return
                self.client.force_login(self.logged_in_user)

            def __call__(self, func):
                @wraps(func)
                def wrapper(*args, **kw):
                    with self:
                        return func(*args, **kw)
                return wrapper

        return ClientUserSwitcher(switch_to)


def get_latex_file_dir(folder_name):
    base_dir = os.path.dirname(__file__)
    return os.path.join(base_dir, "resource", folder_name)


class suppress_stdout_decorator(object):  # noqa
    def __init__(self, suppress_stderr=False):
        self.original_stdout = None
        self.suppress_stderr = None
        self.suppress_stderr = suppress_stderr

    def __enter__(self):
        self.original_stdout = sys.stdout
        sys.stdout = StringIO()

        if self.suppress_stderr:
            self.original_stderr = sys.stderr
            sys.stderr = StringIO()

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self.original_stdout
        if self.suppress_stderr:
            sys.stderr = self.original_stderr

    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kw):
            with self:
                return func(*args, **kw)

        return wrapper


def get_fake_data_url(b64_string, mime_type="image/png"):
    return "data:%s;base64,%s" % (mime_type, b64_string)


def improperly_configured_cache_patch():
    # can be used as context manager or decorator
    built_in_import_path = "builtins.__import__"
    import builtins  # noqa

    built_in_import = builtins.__import__

    def my_disable_cache_import(name, globals=None, locals=None, fromlist=(),
                                level=0):
        if name == "django.core.cache":
            raise ImproperlyConfigured()
        return built_in_import(name, globals, locals, fromlist, level)

    return mock.patch(built_in_import_path, side_effect=my_disable_cache_import)
