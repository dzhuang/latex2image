import io

from django.db import models
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.conf import settings


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


class LatexImage(models.Model):
    tex_key = models.TextField(
        unique=True, blank=False, db_index=True, verbose_name=_('Tex Key'))
    creation_time = models.DateTimeField(
        blank=False, default=now, verbose_name=_('Creation time'))
    image = models.ImageField(
        null=True, blank=True, upload_to="l2i_images")
    data_url = models.TextField(null=True, blank=True, verbose_name=_('Data Url'))
    compile_error = models.TextField(
        null=True, blank=True, verbose_name=_('Compile Error'))
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_('Creator'),
        on_delete=models.CASCADE)

    def save(self, **kwargs):
        # https://stackoverflow.com/a/18803218/3437454
        if self.data_url:
            self.image = make_image_file(self.data_url, self.tex_key)

        self.full_clean()
        return super(LatexImage, self).save(**kwargs)

    def clean(self):
        super(LatexImage, self).clean()

        # Either data_url or compile_error should be saved.
        if self.data_url is not None and self.compile_error is not None:
            raise ValidationError(
                '"data_url" and "compile_error" should '
                'not present at the same time.')
        elif self.data_url is None and self.compile_error is None:
            raise ValidationError(
                '"Either data_url" or "compile_error" should '
                'present.')

    def __repr__(self):
        if self.data_url:
            return "<tex_key:%s, creation_time:%s, data_url:%s>" % (
                self.tex_key, self.creation_time, self.data_url[:50] + "...")
        else:
            return "<tex_key:%s, creation_time:%s, compile_error:%s>" % (
                self.tex_key, self.creation_time, self.compile_error[:50] + "...")
