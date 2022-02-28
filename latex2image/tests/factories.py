from __future__ import division

__copyright__ = "Copyright (C) 2018 Dong Zhuang"

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

import random
import string
from base64 import b64encode

import factory
from django.contrib.auth import get_user_model
from django.utils.timezone import now

from latex.converter import build_key
from latex.models import LatexImage


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()

    username = factory.Sequence(lambda n: "testuser_%03d" % n)
    email = factory.Sequence(lambda n: "test_factory_%03d@example.com" % n)
    password = factory.Sequence(lambda n: "password_%03d" % n)


class LatexImageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LatexImage

    tex_key = factory.Sequence(
        lambda n: build_key("key_%03d" % n, "xelatex", "png"))
    creation_time = factory.LazyFunction(now)
    data_url = factory.LazyAttribute(
        lambda x: "data:image/png;base64,%(b64)s" % {
            "b64": b64encode(''.join(
                [random.SystemRandom().choice("{}{}{}".format(
                    string.ascii_letters, string.digits, string.punctuation))
                    for i in range(50)]).encode()).decode(),
        })
    creator = factory.SubFactory(UserFactory)


class LatexImageErrorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LatexImage

    tex_key = factory.Sequence(
        lambda n: build_key("key_error_%03d" % n, "xelatex", "png"))
    creation_time = factory.LazyFunction(now)
    compile_error = factory.LazyAttribute(
        lambda x: ''.join(
                [random.SystemRandom().choice("{}{}{}".format(
                    string.ascii_letters, string.digits, string.punctuation))
                    for i in range(50)]))
    creator = factory.SubFactory(UserFactory)
