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

import io
from mimetypes import guess_type
from urllib.parse import urljoin

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage, get_storage_class
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.validators import validate_slug
from django.db import models
from django.utils.html import mark_safe
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from latex.utils import get_data_url_from_buf_and_mimetype

UPLOAD_TO = "l2i_images"


def convert_data_url_to_image_obj(data_url):
    from binascii import a2b_base64
    return a2b_base64(data_url)


def make_image_file(data_url, file_base_name):
    output = io.BytesIO(
        convert_data_url_to_image_obj(data_url[data_url.index("base64,") + 7:]))
    mime_type = data_url[5: data_url.index(";")]
    if mime_type == "image/png":
        ext = ".png"
    else:
        ext = ".svg"

    return InMemoryUploadedFile(
        output, 'SVGAndImageFormField', "%s%s" % (file_base_name, ext),
        mime_type, output.tell(), None)


class OverwriteStorage(get_storage_class()):
    def get_available_name(self, name, max_length=None):
        self.delete(name)
        return name


class LatexImage(models.Model):
    tex_key = models.TextField(
        unique=True, blank=False, db_index=True, verbose_name=_('Tex Key'),
        validators=[validate_slug])
    creation_time = models.DateTimeField(
        blank=False, default=now, verbose_name=_('Creation time'))
    image = models.ImageField(
        null=True, blank=True, upload_to=UPLOAD_TO, storage=OverwriteStorage())
    data_url = models.TextField(null=True, blank=True, verbose_name=_('Data Url'))
    compile_error = models.TextField(
        null=True, blank=True, verbose_name=_('Compile Error'))
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_('Creator'),
        on_delete=models.CASCADE)

    class Meta:
        verbose_name = _("LaTeXImage")
        verbose_name_plural = _("LaTeXImages")

    def _get_changed_fields(self):
        # Get updated_fields: https://stackoverflow.com/a/55005137/3437454
        # This method should only be used before saving.
        if self.pk:
            # If self.pk is not None then it's an update.
            cls = self.__class__

            # This will get the current model state since super().save()
            # isn't called yet.
            old = cls.objects.get(pk=self.pk)

            # This gets the newly instantiated Mode object with the new values.
            new = self
            changed_fields = []
            for field in cls._meta.get_fields():
                field_name = field.name
                try:
                    if getattr(old, field_name) != getattr(new, field_name):
                        changed_fields.append(field_name)
                except Exception:
                    # Catch field does not exist exception
                    pass
            return changed_fields
        return []

    def save(self, **kwargs):
        # https://stackoverflow.com/a/18803218/3437454

        changed_fields = self._get_changed_fields()

        if (self.data_url and not self.image) or "data_url" in changed_fields:
            self.image = make_image_file(self.data_url, self.tex_key)

        if self.image and not self.data_url:
            file = default_storage.open(str(self.image))
            self.data_url = get_data_url_from_buf_and_mimetype(
                buf=file.read(), mime_type=guess_type(str(self.image))[0])
            file.close()

        self.full_clean()
        return super().save(**kwargs)

    def clean(self):
        super().clean()

        # Either data_url or compile_error should be saved.
        if self.data_url is not None and self.compile_error is not None:
            raise ValidationError(
                '"data_url" and "compile_error" should '
                'not present at the same time.')
        elif self.data_url is None and self.compile_error is None:
            raise ValidationError(
                '"Either data_url" or "compile_error" should '
                'present.')

    def image_tag(self):
        if self.image:
            pattern = '<img style="max-width: 200px;" src="%s"/>'
            return mark_safe(pattern % urljoin(settings.MEDIA_URL, self.image.url))
        return None

    image_tag.short_description = _('image')

    def __repr__(self):
        if self.data_url:
            return "<tex_key:%s, creation_time:%s, data_url:%s>" % (
                self.tex_key, self.creation_time, self.data_url[:50] + "...")
        else:
            return "<tex_key:%s, creation_time:%s, compile_error:%s>" % (
                self.tex_key, self.creation_time, self.compile_error[:50] + "...")
