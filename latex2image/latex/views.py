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

import sys

from crispy_forms.layout import Submit
from django import forms
from django.contrib.auth.decorators import login_required
from django.db.transaction import atomic
from django.shortcuts import render
from django.utils.translation import gettext as _
from rest_framework import status

from latex.converter import (ALLOWED_COMPILER_FORMAT_COMBINATION,
                             LatexCompileError, tex_to_img_converter)
from latex.models import LatexImage
from latex.utils import StyledFormMixin, get_codemirror_widget


class LatexToImageForm(StyledFormMixin, forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["latex_file"] = forms.FileField(
            label=_("Tex File"), required=False,
        )

        self.fields["latex_code"] = forms.CharField(
            label=_("Tex Code"),
            widget=get_codemirror_widget(),
            required=False,
        )

        self.fields["compiler_format"] = forms.ChoiceField(
            choices=tuple(
                ("2".join([compiler, image_format]),
                 "2".join([compiler, image_format]))
                for compiler, image_format
                in ALLOWED_COMPILER_FORMAT_COMBINATION),
            initial=("xelatex2svg", "xelatex2svg"),
            label=_("compiler and format"),
            required=True)

        self.fields["tex_key"] = forms.CharField(
            required=False,
            help_text=_("Optional. An unique string act as the identifier "
                        "of the LaTeX code. If not specified, it will be "
                        "generated automatically."))

        self.helper.form_class = "form-horizontal"

        self.helper.add_input(
                Submit("convert", _("Convert")))

    def clean(self):
        super().clean()
        if not any([self.cleaned_data.get("latex_file", None),
                    self.cleaned_data.get("latex_code", None)]):
            raise forms.ValidationError(
                _("Either 'Tex File' or 'Tex Code' must be filled.")
            )


@login_required(login_url='/login/')
def request_get_data_url_from_latex_form_request(request):
    instance = None
    ctx = {}
    unknown_error = None
    if request.method == "POST":
        form = LatexToImageForm(request.POST, request.FILES)
        if form.is_valid():
            compiler, image_format = form.cleaned_data["compiler_format"].split("2")
            tex_key = form.cleaned_data["tex_key"] or None

            added_tex_source_to_ctx = False

            f = request.FILES.get("latex_file", None)
            if f:
                f.seek(0)
                tex_source = f.read().decode("utf-8")
                added_tex_source_to_ctx = True
            else:
                tex_source = form.cleaned_data["latex_code"] or None

            if added_tex_source_to_ctx:
                ctx["tex_source"] = tex_source

            _converter = tex_to_img_converter(
                compiler, tex_source, image_format=image_format,
                tex_key=tex_key)

            instance = None

            try:
                instance = LatexImage.objects.get(tex_key=_converter.tex_key)
            except LatexImage.DoesNotExist:
                try:
                    data_url = _converter.get_converted_data_url()
                    instance = LatexImage(
                        tex_key=_converter.tex_key,
                        data_url=data_url,
                        creator=request.user,
                    )
                    with atomic():
                        instance.save()
                except Exception as e:
                    from traceback import print_exc
                    print_exc()

                    tp, err, __ = sys.exc_info()
                    error_str = "%s: %s" % (tp.__name__, str(err))
                    if isinstance(e, LatexCompileError):
                        instance = LatexImage(
                            tex_key=_converter.tex_key,
                            compile_error=error_str,
                            creator=request.user,
                        )
                        with atomic():
                            instance.save()
                    else:
                        unknown_error = ctx["unknown_error"] = error_str

            if instance is not None:
                if instance.image:
                    try:
                        ctx["size"] = instance.image.size
                    except OSError:
                        pass
                ctx["instance"] = instance
                ctx["tex_key"] = instance.tex_key

    else:
        form = LatexToImageForm()

    ctx["form"] = form
    ctx["form_description"] = _("Convert LaTeX code to Image")

    render_kwargs = {
        "request": request,
        "template_name": "latex/latex_form_page.html",
        "context": ctx
    }

    if instance is not None:
        if instance.compile_error:
            render_kwargs["status"] = status.HTTP_400_BAD_REQUEST

    if unknown_error:
        render_kwargs["status"] = status.HTTP_500_INTERNAL_SERVER_ERROR

    return render(**render_kwargs)
