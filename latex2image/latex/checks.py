# -*- coding: utf-8 -*-

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

from latex.utils import get_all_indirect_subclasses
from django.core.checks import register, Critical
from django.core.exceptions import ImproperlyConfigured


class L2ICriticalCheckMessage(Critical):
    def __init__(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        super(L2ICriticalCheckMessage, self).__init__(*args, **kwargs)
        self.obj = self.obj or ImproperlyConfigured.__name__


def bin_check(app_configs, **kwargs):
    """
    Check if all tex compiler and image converter
    are correctly configured, if latex utility is
    enabled.
    """
    from latex.converter import CommandBase

    klass = get_all_indirect_subclasses(CommandBase)
    instance_list = [cls() for cls in klass]
    errors = []
    for instance in instance_list:
        check_errors = instance.check()
        if check_errors:
            errors.extend(check_errors)
    return errors


def settings_check(app_configs, **kwargs):
    errors = []
    from django.conf import settings
    l2i_api_cache_field = getattr(
        settings, "L2I_API_CACHE_FIELD", None)
    if l2i_api_cache_field is not None:
        if not isinstance(l2i_api_cache_field, str):
            errors.append(
                L2ICriticalCheckMessage(
                    msg="if set, settings.L2I_API_CACHE_FIELD "
                        "must be a string",
                    id="cache_mode_e001"))
            return errors
        if l2i_api_cache_field not in ["image", "data_url"]:
            errors.append(
                L2ICriticalCheckMessage(
                    msg="if set, settings.L2I_API_CACHE_FIELD "
                        "must be either 'image' or 'data_url'",
                    id="cache_mode_e002"))
    return errors


def register_startup_checks():
    register(bin_check, "bin_check")
    register(settings_check, "settings_check")
