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

import os
from subprocess import PIPE, Popen
from typing import Any, List, Optional, Text, Tuple  # noqa

from codemirror import CodeMirrorJavascript, CodeMirrorTextarea
from django.core.checks import Critical
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import CommandError
from django.utils.encoding import DEFAULT_LOCALE_ENCODING, force_str
from django.utils.text import format_lazy

# {{{ Constants

ALLOWED_COMPILER = ['latex', 'xelatex', 'xelatex']
ALLOWED_LATEX2IMG_FORMAT = ['png', 'svg']

ALLOWED_COMPILER_FORMAT_COMBINATION = (
    ("latex", "png"),
    ("latex", "svg"),
    ("xelatex", "png"),
    ("xelatex", "png")
)


# }}}


def string_concat(*strings):
    # type: (Any) -> Text
    return format_lazy("{}" * len(strings), *strings)


# {{{ subprocess popen wrapper

def popen_wrapper(args, os_err_exc_type=CommandError,
                  stdout_encoding='utf-8', **kwargs):
    # type: (...) -> Tuple[Text, Text, int]
    """
    Extended from django.core.management.utils.popen_wrapper.
    `**kwargs` is added so that more kwargs can be added.

    This method is especially to solve UnicodeDecodeError
    raised on Windows platform where the OS stdout is not utf-8.

    Friendly wrapper around Popen

    Returns stdout output, stderr output and OS status code.
    """

    try:
        p = Popen(args, stdout=PIPE,
                  stderr=PIPE, close_fds=os.name != 'nt', **kwargs)
    except OSError as e:
        raise os_err_exc_type from e

    output, errors = p.communicate()
    return (
        force_str(output, stdout_encoding, strings_only=True,
                   errors='strict'),
        force_str(errors, DEFAULT_LOCALE_ENCODING,
                   strings_only=True, errors='replace'),
        p.returncode
    )


# }}}


# {{{ file read and write

def file_read(filename):
    # type: (Text) -> bytes
    '''Read the content of a file and close it properly.'''
    with open(filename, 'rb') as f:
        return f.read()


def file_write(filename, content):
    # type: (Text, bytes) -> None
    '''Write into a file and close it properly.'''
    with open(filename, 'wb') as f:
        f.write(content)


# }}}


# {{{ get error log abstracted

LATEX_ERR_LOG_BEGIN_LINE_STARTS = "\n! "
LATEX_ERR_LOG_END_LINE_STARTS = "\nHere is how much of TeX's memory"
LATEX_LOG_OMIT_LINE_STARTS = (
    "See the LaTeX manual or LaTeX",
    "Type  H <return>  for",
    " ...",
    # more
)


def get_abstract_latex_log(log):
    # type: (Text) -> Text
    """abstract error msg from latex compilation log"""
    try:
        msg = log.split(LATEX_ERR_LOG_BEGIN_LINE_STARTS)[1] \
            .split(LATEX_ERR_LOG_END_LINE_STARTS)[0]
    except IndexError:
        return log

    msg = "\n".join(
        line for line in msg.splitlines()
        if (not line.startswith(LATEX_LOG_OMIT_LINE_STARTS) and line.strip() != ""))
    return msg


# }}}


def get_all_indirect_subclasses(cls):
    # type: (Any) -> List[Any]
    all_subcls = []

    for subcls in cls.__subclasses__():
        if not subcls.__subclasses__():
            # has no child
            all_subcls.append(subcls)
        all_subcls.extend(get_all_indirect_subclasses(subcls))

    return list(set(all_subcls))


class CriticalCheckMessage(Critical):
    def __init__(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        super().__init__(*args, **kwargs)
        self.obj = self.obj or ImproperlyConfigured.__name__


def get_codemirror_widget():
    # type: (...) ->  CodeMirrorTextarea

    theme = "default"

    addon_css = ("dialog/dialog",
                 "display/fullscreen",
                 )
    addon_js = ("search/searchcursor",
                "dialog/dialog",
                "search/search",
                "comment/comment",
                "edit/matchbrackets",
                "display/fullscreen",
                "selection/active-line",
                "edit/trailingspace",
                )

    indent_unit = 2

    config = {
        "autofocus": True,
        "fixedGutter": True,
        "matchBrackets": True,
        "styleActiveLine": True,
        "showTrailingSpace": True,
        "indentUnit": indent_unit,
        "readOnly": False,
        "extraKeys": CodeMirrorJavascript("""
                {
                  "Ctrl-/": "toggleComment",
                  "Tab": function(cm)
                  {
                    // from https://github.com/codemirror/CodeMirror/issues/988

                    if (cm.doc.somethingSelected()) {
                        return CodeMirror.Pass;
                    }
                    var spacesPerTab = cm.getOption("indentUnit");
                    var spacesToInsert = (
                        spacesPerTab
                        - (cm.doc.getCursor("start").ch % spacesPerTab));
                    var spaces = Array(spacesToInsert + 1).join(" ");
                    cm.replaceSelection(spaces, "end", "+input");
                  },
                  "Shift-Tab": "indentLess",
                  "F9": function(cm) {
                      cm.setOption("fullScreen",
                        !cm.getOption("fullScreen"));
                  }
                }
            """)
    }

    return CodeMirrorTextarea(
        mode="stex",
        theme=theme,
        addon_css=addon_css,
        addon_js=addon_js,
        config=config)


class StyledFormMixin:
    def __init__(self, *args, **kwargs):
        # type: (...) -> None
        from crispy_forms.helper import FormHelper
        self.helper = FormHelper()
        self._configure_helper()

        super().__init__(*args, **kwargs)

    def _configure_helper(self):
        # type: () -> None
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = "col-lg-2"
        self.helper.field_class = "col-lg-8"


def get_data_url_from_buf_and_mimetype(buf, mime_type):
    from base64 import b64encode
    return "data:%(mime_type)s;base64,%(b64)s" % {
        "mime_type": mime_type,
        "b64": b64encode(buf).decode(),
    }

# vim: foldmethod=marker
