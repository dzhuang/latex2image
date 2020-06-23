from __future__ import division

from unittest.case import TestCase

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

from latex.converter import CommandBase, Latexmk, Pdf2svg
from django.test import SimpleTestCase
from django.test.utils import override_settings

from unittest import mock


class CheckL2ISettingsBase(SimpleTestCase):
    @property
    def func(self):
        from latex.checks import bin_check
        return bin_check

    @property
    def msg_id_prefix(self):
        raise NotImplementedError()

    def assertCheckMessages(self,  # noqa
                            expected_ids=None, expected_msgs=None, length=None,
                            filter_message_id_prefixes=None, ignore_order=False):
        """
        Check the run check result of the setting item of the testcase instance
        :param expected_ids: Optional, list of expected message id,
        default to None
        :param expected_msgs: Optional, list of expected message string,
        default to None
        :param length: Optional, length of expected check message,
        default to None
        :param filter_message_id_prefixes: a list or tuple of message id prefix,
        to restrict the
         run check result to be within the iterable.
        """
        if not filter_message_id_prefixes:
            filter_message_id_prefixes = self.msg_id_prefix
            if isinstance(filter_message_id_prefixes, str):
                filter_message_id_prefixes = [filter_message_id_prefixes]
            assert isinstance(filter_message_id_prefixes, (list, tuple))

        if expected_ids is None and expected_msgs is None and length is None:
            raise RuntimeError("At least one parameter should be specified "
                               "to make the assertion")

        result = self.func(None)

        def is_id_in_filter(id, filter):
            prefix = id.split(".")[0]
            return prefix in filter

        try:
            result_ids, result_msgs = (
                list(zip(
                    *[(r.id, r.msg) for r in result
                      if is_id_in_filter(r.id, filter_message_id_prefixes)])))

            if expected_ids is not None:
                assert isinstance(expected_ids, (list, tuple))
                if ignore_order:
                    result_ids = tuple(sorted(list(result_ids)))
                    expected_ids = sorted(list(expected_ids))
                self.assertEqual(result_ids, tuple(expected_ids))

            if expected_msgs is not None:
                assert isinstance(expected_msgs, (list, tuple))
                if ignore_order:
                    result_msgs = tuple(sorted(list(result_msgs)))
                    expected_msgs = sorted(list(expected_msgs))
                self.assertEqual(result_msgs, tuple(expected_msgs))

            if length is not None:
                self.assertEqual(len(expected_ids), len(result_ids))
        except ValueError as e:
            if "values to unpack" in str(e):
                if expected_ids or expected_msgs or length:
                    self.fail("Check message unexpectedly found to be empty")
            else:
                raise


class CheckBin(CheckL2ISettingsBase):
    msg_id_prefix = ""

    @property
    def func(self):
        from latex.checks import bin_check
        return bin_check

    def test_checks(self):
        self.assertCheckMessages([])


class CheckCacheField(CheckL2ISettingsBase):
    # test L2I_API_IMAGE_RETURNS_RELATIVE_PATH
    msg_id_prefix = "api_image_returns_relative_path"

    @property
    def func(self):
        from latex.checks import settings_check
        return settings_check

    @override_settings(L2I_API_IMAGE_RETURNS_RELATIVE_PATH=None)
    def test_checks_none(self):
        self.assertCheckMessages([])

    @override_settings(L2I_API_IMAGE_RETURNS_RELATIVE_PATH=1)
    def test_checks_not_bool(self):
        self.assertCheckMessages(['api_image_returns_relative_path.E001'])

    @override_settings(L2I_API_IMAGE_RETURNS_RELATIVE_PATH=True)
    def test_checks_ok(self):
        self.assertCheckMessages([])

    @override_settings(L2I_API_IMAGE_RETURNS_RELATIVE_PATH=False)
    def test_checks_ok2(self):
        self.assertCheckMessages([])


class CheckImageMagickPngResolution(CheckL2ISettingsBase):
    # test L2I_IMAGEMAGICK_PNG_RESOLUTION
    msg_id_prefix = "imagemagick_png_resolution"

    @property
    def func(self):
        from latex.checks import settings_check
        return settings_check

    @override_settings(L2I_IMAGEMAGICK_PNG_RESOLUTION=None)
    def test_checks_none(self):
        self.assertCheckMessages([])

    @override_settings(L2I_IMAGEMAGICK_PNG_RESOLUTION=[1])
    def test_checks_list(self):
        self.assertCheckMessages(['imagemagick_png_resolution.E001'])

    @override_settings(L2I_IMAGEMAGICK_PNG_RESOLUTION="90")
    def test_checks_int_str_ok(self):
        self.assertCheckMessages([])

    @override_settings(L2I_IMAGEMAGICK_PNG_RESOLUTION=90)
    def test_checks_ok(self):
        self.assertCheckMessages([])

    @override_settings(L2I_IMAGEMAGICK_PNG_RESOLUTION="big")
    def test_checks_not_int(self):
        self.assertCheckMessages(['imagemagick_png_resolution.E001'])

    @override_settings(L2I_IMAGEMAGICK_PNG_RESOLUTION="-1")
    def test_checks_negative(self):
        self.assertCheckMessages(['imagemagick_png_resolution.E001'])


class VersionCheckTest(TestCase):
    def test_check_version_error(self):
        class FakeCommand1(CommandBase):
            name = "noneexist"
            cmd = "nonexist"

        fake_command = FakeCommand1()
        errors = fake_command.check()
        self.assertEqual(len(errors), 1)


class VersionCheckTestMocked(TestCase):
    def setUp(self) -> None:
        version_popen = mock.patch(
            "latex.converter.CommandBase.version_popen")
        self.mock_version_popen = version_popen.start()
        self.mock_version_popen.start()
        self.mock_version_popen.return_value = ("4.39", "some error", 0)
        self.addCleanup(version_popen.stop)

    def test_below_min_version(self):
        class FakeLatexmk1(Latexmk):
            min_version = "100.39"

        fake_command = FakeLatexmk1()
        errors = fake_command.check()
        self.assertEqual(len(errors), 1)

    def test_above_min_version(self):
        class FakeLatexmk1(Latexmk):
            min_version = "0.39"

        fake_command = FakeLatexmk1()
        errors = fake_command.check()
        self.assertEqual(len(errors), 0)

    def test_equal_min_version(self):
        class FakeLatexmk1(Latexmk):
            min_version = "4.39"

        fake_command = FakeLatexmk1()
        errors = fake_command.check()
        self.assertEqual(len(errors), 0)

    def test_min_version_error(self):
        class FakeLatexmk1(Latexmk):
            min_version = "100.39"

        fake_command = FakeLatexmk1()
        errors = fake_command.check()
        self.assertEqual(len(errors), 1)

    def test_max_version_error(self):
        class FakeLatexmk2(Latexmk):
            max_version = "1.39"

        fake_command = FakeLatexmk2()
        errors = fake_command.check()
        self.assertEqual(len(errors), 1)

    def test_max_version_equal(self):
        class FakeLatexmk2(Latexmk):
            max_version = "4.39"
        fake_command = FakeLatexmk2()
        errors = fake_command.check()
        self.assertEqual(len(errors), 0)

    def test_max_version_fit(self):
        class FakeLatexmk2(Latexmk):
            max_version = "4.40"
        fake_command = FakeLatexmk2()
        errors = fake_command.check()
        self.assertEqual(len(errors), 0)

    def test_pdf2svg_with_version_check_error(self):
        class FakePdf2svg(Pdf2svg):
            skip_version_check = False

        self.mock_version_popen.return_value = "foobar", "error", 1

        fake_command = FakePdf2svg()
        errors = fake_command.check()
        self.assertEqual(len(errors), 1)
