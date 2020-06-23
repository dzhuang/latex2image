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

from latex.utils import get_all_indirect_subclasses, CriticalCheckMessage
from django.core.checks import register


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
        errors.extend(instance.check())
    return errors


def settings_check(app_configs, **kwargs):
    errors = []
    from django.conf import settings
    api_image_returns_relative_path = getattr(
        settings, "L2I_API_IMAGE_RETURNS_RELATIVE_PATH", None)
    if api_image_returns_relative_path is not None:
        if not isinstance(api_image_returns_relative_path, bool):
            errors.append(
                CriticalCheckMessage(
                    msg="if set, settings.L2I_API_IMAGE_RETURNS_RELATIVE_PATH "
                        "must be a bool value",
                    id="api_image_returns_relative_path.E001"))

    imagemagick_png_resolution = (
        getattr(settings, "L2I_IMAGEMAGICK_PNG_RESOLUTION", None))
    if imagemagick_png_resolution is not None:
        try:
            assert int(imagemagick_png_resolution) > 0
        except Exception:
            errors.append(
                CriticalCheckMessage(
                    msg="if set, settings.L2I_IMAGEMAGICK_PNG_RESOLUTION "
                        "must be a positive int",
                    id="imagemagick_png_resolution.E001"))
    return errors


def register_startup_checks():
    register(bin_check, "bin_check")
    register(settings_check, "settings_check")
