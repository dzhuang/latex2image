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

import errno
import os
import re
import shutil
import sys
from hashlib import md5

from django.core.management.base import CommandError
from django.utils.encoding import DEFAULT_LOCALE_ENCODING
from django.utils.translation import gettext as _
from wand.image import Image as wand_image

from latex.constants import (ALLOWED_COMPILER,
                             ALLOWED_COMPILER_FORMAT_COMBINATION,
                             ALLOWED_LATEX2IMG_FORMAT)
from latex.utils import (CriticalCheckMessage, file_read, file_write,
                         get_abstract_latex_log,
                         get_data_url_from_buf_and_mimetype, popen_wrapper,
                         string_concat)

debug = False

from typing import TYPE_CHECKING, Any, List, Optional, Text  # noqa

if TYPE_CHECKING:
    from django.core.checks.messages import CheckMessage  # noqa


TIKZ_PGF_RE = re.compile(r"\\begin\{(?:tikzpicture|pgfpicture)\}")


class LatexCompileError(RuntimeError):
    pass


class UnknownCompileError(RuntimeError):
    pass


class ImageConvertError(RuntimeError):
    pass


# {{{ latex compiler classes and image converter classes


class CommandBase(object):
    @property
    def name(self):
        # type: () -> Text
        """
        The name of the command tool
        """
        raise NotImplementedError

    @property
    def cmd(self):
        # type: () -> Text
        """
        The string of the command
        """
        raise NotImplementedError

    @property
    def skip_version_check(self):
        # type: () -> bool
        return False

    min_version = None  # type: Optional[Text]
    max_version = None  # type: Optional[Text]
    bin_path = ""  # type: Text

    def __init__(self):
        # type: () -> None
        self.bin_path = self.get_bin_path()

    def get_bin_path(self):
        return self.cmd.lower()

    def version_popen(self):
        return popen_wrapper(
            [self.bin_path, '--version'],
            stdout_encoding=DEFAULT_LOCALE_ENCODING
        )

    def check(self):
        # type: () -> List[CheckMessage]
        errors = []

        self.bin_path = self.get_bin_path()

        try:
            out, err, status = self.version_popen()
        except CommandError as e:
            errors.append(CriticalCheckMessage(
                msg=e.__str__(),
                hint=("Unable to run '%(cmd)s with '--version'. Is "
                      "%(tool)s installed or has its "
                      "path correctly configured "
                      "in local_settings.py?") % {
                         "cmd": self.cmd,
                         "tool": self.name,
                     },
                obj=self.name,
                id="%s.E001" % self.name.lower()
            ))
            return errors

        if self.skip_version_check:
            return errors

        m = re.search(r'(\d+)\.(\d+)\.?(\d+)?', out)

        if not m:
            errors.append(CriticalCheckMessage(
                msg="\n".join([out, err]),
                hint=("Unable find the version of '%(cmd)s'. Is "
                      "%(tool)s installed with the correct version?"
                      ) % {
                         "cmd": self.cmd,
                         "tool": self.name,
                     },
                obj=self.name,
                id="%s.E002" % self.name.lower()
            ))
        else:
            version = ".".join(d for d in m.groups() if d)
            from pkg_resources import parse_version
            if self.min_version:
                if parse_version(version) < parse_version(self.min_version):
                    errors.append(CriticalCheckMessage(
                        "Version outdated",
                        hint=("'%(tool)s' with version "
                              ">=%(required)s is required, "
                              "current version is %(version)s"
                              ) % {
                                 "tool": self.name,
                                 "required": self.min_version,
                                 "version": version},
                        obj=self.name,
                        id="%s.E003" % self.name.lower()
                    ))
            if self.max_version:
                if parse_version(version) > parse_version(self.max_version):
                    errors.append(CriticalCheckMessage(
                        "Version not supported",
                        hint=("'%(tool)s' with version "
                              "< %(max_version)s is required, "
                              "current version is %(version)s"
                              ) % {
                                 "tool": self.name,
                                 "max_version": self.max_version,
                                 "version": version},
                        obj=self.name,
                        id="%s.E004" % self.name.lower()
                    ))
        return errors


class TexCompilerBase(CommandBase):
    pass


class Latexmk(TexCompilerBase):
    name = "latexmk"
    cmd = "latexmk"

    # This also require perl, ActivePerl is recommended
    min_version = "4.39"


class LatexCompiler(TexCompilerBase):
    latexmk_option = [
        '-latexoption="-no-shell-escape"',
        '-interaction=nonstopmode',
        '-halt-on-error'
    ]

    @property
    def output_format(self):
        # type: () -> Text
        raise NotImplementedError()

    def __init__(self):
        # type: () -> None
        super().__init__()
        self.latexmk_prog_repl = self._get_latexmk_prog_repl()

    def _get_latexmk_prog_repl(self):
        # type: () -> Text
        """
        Program replace when using "-pdflatex=" or "-latex="
        arg in latexmk, especially needed when compilers are
        not in system's default $PATH.
        :return: the latexmk arg "-pdflatex=/path/to/pdflatex" for
        # pdflatex or "-pdflatex=/path/to/xelatex" for xelatex
        """
        return (
            "-%s=%s" % (self.name.lower(), self.bin_path.lower())
        )

    def get_latexmk_subpro_cmdline(self, input_path):
        # type: (Text) -> List[Text]
        latexmk = Latexmk()
        args = [
            latexmk.bin_path,
            "-%s" % self.output_format,
            self.latexmk_prog_repl,
        ]
        args.extend(self.latexmk_option)
        args.append(input_path)

        return args


class Latex(LatexCompiler):
    name = "latex"
    cmd = "latex"
    output_format = "dvi"


class PdfLatex(LatexCompiler):
    name = "PdfLatex"
    cmd = "pdflatex"
    output_format = "pdf"


class LuaLatex(LatexCompiler):
    name = "LuaLatex"
    cmd = "lualatex"
    output_format = "pdf"

    def __init__(self):
        # type: () -> None
        super().__init__()
        self.latexmk_prog_repl = "-%s=%s" % ("pdflatex", self.bin_path)
        if sys.platform.startswith("win"):  # pragma: no cover
            self.latexmk_prog_repl = "-%s=%s" % ("pdflatex", "lualatex-dev")


class XeLatex(LatexCompiler):
    name = "XeLatex"
    cmd = "xelatex"
    output_format = "pdf"

    def __init__(self):
        # type: () -> None
        super().__init__()
        self.latexmk_prog_repl = "-%s=%s" % ("pdflatex", self.bin_path)


class ImageConverter(CommandBase):

    @property
    def output_format(self):
        # type: () -> Text
        raise NotImplementedError

    @staticmethod
    def convert_popen(cmdline, cwd):
        return popen_wrapper(cmdline, cwd=cwd)

    def do_convert(self, compiled_file_path, image_path, working_dir):
        cmdlines = self._get_convert_cmdlines(
            compiled_file_path, image_path)

        status = None
        error = None
        for cmdline in cmdlines:
            _output, error, status = self.convert_popen(
                cmdline,
                cwd=working_dir
            )
            if status != 0:
                return False, error

        return status == 0, error

    def _get_convert_cmdlines(
            self, input_filepath, output_filepath):
        # type: (Text, Text) -> List[List[Text]]
        raise NotImplementedError


class Dvipng(TexCompilerBase, ImageConverter):
    # Inheritate TexCompilerBase's bin_path
    # since dvipng is usually installed in
    # latex compilers' bin dir.
    name = "dvipng"
    cmd = "dvipng"
    output_format = "png"

    def _get_convert_cmdlines(
            self, input_filepath, output_filepath):
        # type: (Text, Text) -> List[List[Text]]
        return [[self.bin_path,
                 '-o', output_filepath,
                 '-pp', '1',
                 '-T', 'tight',
                 '-z9',
                 input_filepath]]


class Dvisvg(TexCompilerBase, ImageConverter):
    # Inheritate TexCompilerBase's bin_path
    # since dvisvgm is usually installed in
    # latex compilers' bin dir.
    name = "dvisvg"
    cmd = "dvisvgm"
    output_format = "svg"

    def _get_convert_cmdlines(
            self, input_filepath, output_filepath):
        # type: (Text, Text) -> List[List[Text]]
        return [[self.bin_path,
                 '--no-fonts',
                 '-o', output_filepath,
                 input_filepath]]


class Pdf2svg(TexCompilerBase, ImageConverter):
    name = "pdf2svg"
    cmd = "pdf2svg"
    output_format = "svg"

    # pdf2svg has no version
    skip_version_check = True

    def _get_convert_cmdlines(
            self, input_filepath, output_filepath):
        # type: (Text, Text) -> List[List[Text]]
        return [
            ["pdfcrop", input_filepath, input_filepath],
            [self.bin_path, input_filepath, output_filepath]
        ]


class ImageMagick(ImageConverter):
    name = "ImageMagick"
    cmd = "convert"
    output_format = "png"

    def get_bin_path(self):
        if sys.platform.startswith("win"):  # pragma: no cover, this happens when debugging  # noqa
            from wand.api import library_paths
            for p in library_paths():
                if p[0]:
                    bin_path_dir = os.path.dirname(p[0])
                    return os.path.join(bin_path_dir, self.cmd.lower())
        else:
            return super().get_bin_path()

    def do_convert(self, compiled_file_path, image_path, working_dir):
        success = True
        error = ""
        try:
            from django.conf import settings
            resolution = int(
                getattr(settings, "L2I_IMAGEMAGICK_PNG_RESOLUTION", 96))
            with wand_image(
                    filename=compiled_file_path, resolution=resolution
            ) as original:
                with original.convert(self.output_format) as converted:
                    converted.trim()
                    converted.save(filename=image_path)
        except Exception as e:
            success = False
            error = "%s: %s" % (type(e).__name__, str(e))

        return success, error

# }}}


# {{{ convert file to data url

def get_data_url(file_path):
    # type: (Text) -> Text
    """
    Convert file to data URL
    """
    buf = file_read(file_path)

    from mimetypes import guess_type
    mime_type = guess_type(file_path)[0]

    return get_data_url_from_buf_and_mimetype(buf, mime_type)


# }}}


# {{{ Base tex2img class

def build_key(tex_source, cmd, image_format):
    from django.conf import settings
    version = getattr(settings, "L2I_KEY_VERSION", 1)

    return "%s_%s_%s_v%s" % (
        md5(tex_source.encode("utf-8")).hexdigest(),
        cmd, image_format, version)


class Tex2ImgBase(object):
    """The abstract class of converting tex source to images.
    """

    @property
    def compiler(self):
        # type: () -> LatexCompiler
        """
        :return: an instance of `LatexCompiler`
        """
        raise NotImplementedError()

    @property
    def converter(self):
        # type: () -> ImageConverter
        """
        :return: an instance of `ImageConverter`
        """
        raise NotImplementedError()

    def __init__(self, tex_source, tex_key=None, force_overwrite=False):
        # type: (...) -> None
        """
        :param tex_source: Required, a string representing the
        full tex source code.
        :param tex_key: a string which is the identifier of
        the tex_source, if None, it will be generated using
        `tex_source`.
        """

        tex_source = tex_source.strip()
        assert isinstance(tex_source, str)

        self.tex_source = tex_source
        self.working_dir = None

        self.image_format = (
            self.converter.output_format.replace(".", "").lower())
        self.image_ext = ".%s" % self.image_format

        self.compiled_ext = (
                ".%s" % self.compiler.output_format.replace(".", "").lower())

        if tex_key is None:
            tex_key = build_key(
                self.tex_source,
                self.compiler.cmd, self.image_format
            )
        self.tex_key = tex_key
        self.force_overwrite = force_overwrite

    def get_compiler_cmdline(self, tex_path):
        # type: (Text) -> List[Text]
        return self.compiler.get_latexmk_subpro_cmdline(tex_path)

    def save_source(self):  # pragma: no cover, this happens when debugging
        file_name = self.tex_key + ".tex"
        from django.conf import settings
        BASE_DIR = getattr(settings, "BASE_DIR")
        folder = os.path.join(BASE_DIR, "test_tex")

        try:
            os.makedirs(folder)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
        file_path = os.path.join(folder, file_name)
        file_write(file_path, self.tex_source.encode())

    def _remove_working_dir(self):
        # type: () -> None
        if debug:
            self.save_source()

        if self.working_dir:
            if debug:
                print(self.working_dir)
            else:
                shutil.rmtree(self.working_dir)

    def compile_popen(self, cmdline):
        # This method is introduced for facilitating subprocess tests.
        return popen_wrapper(cmdline, cwd=self.working_dir)

    def get_compiled_file(self):
        # type: () -> Optional[Text]
        """
        Compile latex source.
        :return: string, the path of the compiled file if succeeded.
        """
        from tempfile import mkdtemp

        # https://github.com/python/mypy/issues/1833
        self.working_dir = mkdtemp(prefix="LATEX_")  # type: ignore

        assert self.tex_key is not None
        assert self.working_dir is not None
        tex_filename_to_compile = self.tex_key + ".tex"
        tex_path = os.path.join(self.working_dir, tex_filename_to_compile)
        file_write(tex_path, self.tex_source.encode('UTF-8'))

        assert tex_path is not None
        log_path = tex_path.replace(".tex", ".log")
        compiled_file_path = tex_path.replace(
            ".tex", self.compiled_ext)

        cmdline = self.get_compiler_cmdline(tex_path)
        output, error, status = self.compile_popen(cmdline)

        if status != 0:
            try:
                log = file_read(log_path).decode("utf-8")
            except OSError:
                # no log file is generated
                self._remove_working_dir()
                raise LatexCompileError(error)

            log = get_abstract_latex_log(log).replace("\\n", "\n").strip()
            self._remove_working_dir()
            raise LatexCompileError(log)

        if os.path.isfile(compiled_file_path):
            return compiled_file_path
        else:
            self._remove_working_dir()

            raise UnknownCompileError(
                string_concat(
                    ("%s." % error) if error else "",
                    _('No %s file was generated.')
                    % self.compiler.output_format)
            )

    def get_converted_data_url(self):
        # type: () -> Optional[Text]
        """
        Convert compiled file into image.
        :return: string, the data_url
        """
        compiled_file_path = self.get_compiled_file()
        assert compiled_file_path

        image_path = compiled_file_path.replace(
            self.compiled_ext,
            self.image_ext)

        convert_success, error = self.converter.do_convert(
            compiled_file_path, image_path, self.working_dir)

        if not convert_success:
            self._remove_working_dir()
            raise ImageConvertError(error)

        n_images = get_number_of_images(image_path, self.image_ext)

        if n_images == 0:
            raise ImageConvertError(
                _("No image was generated at %s" % self.working_dir))
        elif n_images > 1:
            raise ImageConvertError(
                string_concat(
                    "%s images are generated while expecting 1, "
                    "possibly due to long pdf file."
                    % (n_images, )
                ))

        try:
            data_url = get_data_url(image_path)
        except Exception as e:
            raise ImageConvertError(
                "%s:%s" % (type(e).__name__, str(e))
            )
        finally:
            self._remove_working_dir()

        return data_url

# }}}


# {{{ derived tex2img converter

class Latex2Svg(Tex2ImgBase):
    compiler = Latex()
    converter = Dvisvg()


class Lualatex2Png(Tex2ImgBase):
    compiler = LuaLatex()
    converter = ImageMagick()


class Latex2Png(Tex2ImgBase):
    compiler = Latex()
    converter = Dvipng()


class Pdflatex2Png(Tex2ImgBase):
    compiler = PdfLatex()
    converter = ImageMagick()


class Pdflatex2Svg(Tex2ImgBase):
    compiler = PdfLatex()
    converter = Pdf2svg()


class Lualatex2Svg(Tex2ImgBase):
    compiler = LuaLatex()
    converter = Pdf2svg()


class Xelatex2Png(Tex2ImgBase):
    compiler = XeLatex()
    converter = ImageMagick()


class Xelatex2Svg(Tex2ImgBase):
    compiler = XeLatex()
    converter = Pdf2svg()

# }}}


# {{{ get tex2img class


def get_tex2img_class(compiler, image_format):
    # type: (Text, Text) -> Any
    image_format = image_format.replace(".", "").lower()
    compiler = compiler.lower()
    if image_format not in ALLOWED_LATEX2IMG_FORMAT:
        raise ValueError(
            _("Unsupported image format '%s'") % image_format)

    if compiler not in ALLOWED_COMPILER:
        raise ValueError(
            _("Unsupported tex compiler '%s'") % compiler)

    if not (compiler, image_format) in ALLOWED_COMPILER_FORMAT_COMBINATION:
        raise ValueError(
            _("Unsupported combination: "
              "('%(compiler)s', '%(format)s'). "
              "Currently support %(supported)s.")
            % {"compiler": compiler,
               "format": image_format,
               "supported": ", ".join(
                   str(e) for e in ALLOWED_COMPILER_FORMAT_COMBINATION)}
        )

    class_name = "%s2%s" % (compiler.title(), image_format.title())

    return getattr(sys.modules[__name__], class_name)

# }}}


# {{{ check if multiple images are generated due to long pdf

def get_number_of_images(image_path, image_ext):
    # type: (Text, Text) -> int
    if os.path.isfile(image_path):
        return 1
    count = 0
    while True:
        try_path = (
            "%(image_path)s-%(number)d%(ext)s"
            % {"image_path": image_path.replace(image_ext, ""),
               "number": count,
               "ext": image_ext
               }
        )
        if not os.path.isfile(try_path):
            break
        count += 1

    return count

# }}}


def tex_to_img_converter(
        compiler, tex_source, image_format, tex_key=None, **kwargs):
    # type: (Text, Text, Text, Optional[Text], **Any) -> Tex2ImgBase
    '''Convert LaTeX to IMG tag'''

    # https://lists.gnu.org/archive/html/dvipng/2010-11/msg00001.html
    if (compiler == "latex" and image_format == "png"
            and re.search(TIKZ_PGF_RE, tex_source)):
        image_format = "svg"

    assert isinstance(compiler, str)

    tex2img_class = get_tex2img_class(compiler, image_format)  # type: ignore

    latex2img = tex2img_class(
        tex_source=tex_source,
        tex_key=tex_key,
        )

    return latex2img


# vim: foldmethod=marker
