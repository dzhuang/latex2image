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


from crispy_forms.layout import Button, Submit
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm as AuthForm
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext as _
from rest_framework.authtoken.models import Token

from latex.utils import StyledFormMixin


class AuthenticationForm(StyledFormMixin, AuthForm):
    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request=request, *args, **kwargs)
        self.helper.add_input(
                Submit("login", _("Login")))


class UserForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        token = kwargs.pop("token", None)
        super().__init__(*args, **kwargs)

        self.fields["api_token"] = forms.CharField()
        self.fields["api_token"].widget.attrs['readonly'] = True
        self.fields["api_token"].required = False
        self.fields["api_token"].initial = token

        self.fields["username"].required = True

        self.helper.add_input(
            Submit("submit", _("Submit")))

        self.helper.add_input(
                Button("logout", _("Sign out"), css_class="btn btn-danger",
                       onclick=(
                           "window.location.href='%s'"
                           % reverse("logout"))))


@login_required(login_url='/login/')
def user_profile(request):
    user_form = None

    user = request.user
    tokens = Token.objects.filter(user=user)
    token = None
    if tokens.count():
        token = tokens[0]

    if request.method == "POST":
        if "submit" in request.POST:
            user_form = UserForm(
                    request.POST,
                    instance=user,
                    token=token,
            )
            if user_form.is_valid():
                user_form.save(commit=True)

    if user_form is None:
        request.user.refresh_from_db()
        user_form = UserForm(
            instance=user,
            token=token,
        )

    return render(request, "generic_form_page.html", {
        "form": user_form,
        "form_description": _("User Profile"),
        })
