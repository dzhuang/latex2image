import sys

from urllib.parse import urljoin

from crispy_forms.layout import Submit, Button
from django.core.exceptions import ImproperlyConfigured
from django.db.models.fields.files import ImageFieldFile
from django.conf import settings
from django import forms
from django.utils.translation import ugettext as _
from django.contrib.auth.forms import AuthenticationForm as AuthForm
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse
from django.http import JsonResponse
from django.utils.encoding import filepath_to_uri

from rest_framework.parsers import JSONParser
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.authtoken.models import Token

from latex.models import LatexImage
from latex.serializers import LatexImageSerializer
from latex.converter import (
    tex_to_img_converter, LatexCompileError, ALLOWED_COMPILER_FORMAT_COMBINATION,
)
from latex.utils import get_codemirror_widget


def get_cached_attribute_by_tex_key(tex_key, attr, request=None):
    if attr != getattr(settings, "L2I_API_CACHE_FIELD", None):
        return {}

    try:
        import django.core.cache as cache

        def_cache = cache.caches["default"]
        cache_key = tex_key
        error_key = "%s_error" % cache_key
    except ImproperlyConfigured:
        return None

    assert cache_key is not None

    result_dict = {}

    def update_image_url_absolute_url(_result_dict, _request):
        # When image is requested to be cached, make sure image url is
        # an absolute url irrespective of MEDIA_URL changes.
        if "image" in _result_dict and _request is not None:
            _result_dict["image"] = (
                request.build_absolute_uri(
                    urljoin(
                        settings.MEDIA_URL,
                        filepath_to_uri(_result_dict["image"]))
                ))

    attr_value = def_cache.get(cache_key)

    compile_error_key = def_cache.get(error_key)
    if attr_value is not None:
        assert compile_error_key is None
        result_dict[attr] = attr_value
        update_image_url_absolute_url(result_dict, request)
        return result_dict

    elif compile_error_key is not None:
        assert attr_value is None
        result_dict["compile_error"] = compile_error_key
        return result_dict

    # Check db if it exists
    objs = LatexImage.objects.filter(tex_key=tex_key)
    if not objs.count():
        return {}

    obj = objs[0]
    if obj.compile_error:
        result_dict["compile_error"] = obj.compile_error
        def_cache.add(error_key, obj.compile_error, None)
        return result_dict

    attr_value = getattr(obj, attr)

    assert attr_value is not None, \
        "Attribute %s of %s can't be None" % (str(obj), attr)

    # For Image, we cache its url
    if isinstance(attr_value, ImageFieldFile):
        attr_value = str(attr_value)

    # ignore attribute value with size (byte) over L2I_CACHE_MAX_BYTES
    if len(attr_value) <= getattr(settings, "L2I_CACHE_MAX_BYTES", 0):
        def_cache.add(cache_key, attr_value, None)

    result_dict[attr] = attr_value
    update_image_url_absolute_url(result_dict, request)
    return result_dict


class StyledFormMixin:
    def __init__(self, *args, **kwargs):
        # type: (...) -> None
        from crispy_forms.helper import FormHelper
        self.helper = FormHelper()
        self._configure_helper()

        super(StyledFormMixin, self).__init__(*args, **kwargs)

    def _configure_helper(self):
        # type: () -> None
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = "col-lg-2"
        self.helper.field_class = "col-lg-8"


class LatexToImageForm(StyledFormMixin, forms.Form):
    def __init__(self, *args, **kwargs):
        super(LatexToImageForm, self).__init__(*args, **kwargs)

        self.fields["latex_file"] = forms.FileField(
            label=_("Tex File"), required=False,
        )

        self.fields["latex_code"] = forms.CharField(
            label=_("Tex Code"),
            widget=get_codemirror_widget(),
            required=False,
        )

        self.fields["compiler_format"] = forms.ChoiceField(
            choices=tuple(("2".join([compiler, image_format]), "2".join([compiler, image_format]))
                          for compiler, image_format in ALLOWED_COMPILER_FORMAT_COMBINATION),
            initial=("xelatex2svg", "xelatex2svg"),
            label=_("compiler"),
            required=True)

        self.fields["tex_key"] = forms.CharField(
            required=False)

        self.helper.add_input(
                Submit("convert", _("Convert")))

    def clean(self):
        super(LatexToImageForm, self).clean()
        if not any([self.cleaned_data.get("latex_file", None),
                    self.cleaned_data.get("latex_code", None)]):
            raise forms.ValidationError(
                _("Either 'Tex File' or 'Tex Code' must be filled.")
            )


@login_required(login_url='/login/')
def request_get_data_url_from_latex_form_request(request):
    ctx = {}
    if request.method == "POST":
        form = LatexToImageForm(request.POST, request.FILES)
        if form.is_valid():
            compiler, image_format = form.cleaned_data["compiler_format"].split("2")
            tex_key = form.cleaned_data["tex_key"] or None

            tex_source = form.cleaned_data["latex_code"] or None

            added_tex_source_to_ctx = False

            if tex_source is None:
                f = request.FILES["latex_file"]
                f.seek(0)
                tex_source = f.read().decode("utf-8")
                added_tex_source_to_ctx = True

            if added_tex_source_to_ctx:
                ctx["tex_source"] = tex_source

            _converter = tex_to_img_converter(
                compiler, tex_source, image_format=image_format,
                tex_key=tex_key)

            try:
                instance = LatexImage.objects.get(tex_key=_converter.tex_key)
                if instance.compile_error:
                    ctx["error"] = instance.compile_error
                ctx["data_url"] = instance.data_url

            except LatexImage.DoesNotExist:
                try:
                    data_url = _converter.get_converted_data_url()
                    new_instance = LatexImage(
                        tex_key=_converter.tex_key,
                        data_url=data_url,
                        creator=request.user,
                    )
                    new_instance.save()

                except Exception as e:
                    from traceback import print_exc
                    print_exc()

                    tp, err, __ = sys.exc_info()
                    error_str = "%s: %s" % (tp.__name__, str(err))
                    ctx["error"] = error_str
                    if isinstance(e, LatexCompileError):
                        new_instance = LatexImage(
                            tex_key=_converter.tex_key,
                            compile_error=error_str,
                            creator=request.user,
                        )
                        new_instance.save()
                else:
                    ctx["data_url"] = data_url

    else:
        form = LatexToImageForm()

    ctx["form"] = form
    ctx["form_description"] = _("Convert Latex code to DataUrl")

    return render(request, "latex/latex_form_page.html", ctx)


class AuthenticationForm(StyledFormMixin, AuthForm):
    def __init__(self, request=None, *args, **kwargs):
        super(AuthenticationForm, self).__init__(request=request, *args, **kwargs)
        self.helper.add_input(
                Submit("login", _("Login")))


class UserForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        token = kwargs.pop("token", None)
        super(UserForm, self).__init__(*args, **kwargs)

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


class FieldsSerializerMixin:
    def get_serializer(self, *args, **kwargs):
        fields = self.request.GET.getlist('fields')
        if fields:
            kwargs["fields"] = fields[0]
        return super(FieldsSerializerMixin, self).get_serializer(*args, **kwargs)


def get_cached_results_from_request_field_and_tex_key(request, tex_key, field_str):
    """
    This currently deal with single field ('image' or 'data_url') cache
    """
    cached_result = None
    fields = field_str.split(",")
    if len(fields) == 1:
        cached_result = get_cached_attribute_by_tex_key(
            tex_key, fields[0], request=request)
    return cached_result


class CreateMixin:
    def create(self, request, *args, **kwargs):
        try:
            req_params = JSONParser().parse(request)
            compiler = req_params.pop("compiler")
            tex_source = req_params.pop("tex_source")
            image_format = req_params.pop("image_format")
            tex_key = req_params.pop("tex_key", None)
            field_str = req_params.pop("fields", None)
        except Exception:
            from traceback import print_exc
            print_exc()
            tp, e, __ = sys.exc_info()
            error = "%s: %s" % (tp.__name__, str(e))
            return Response({"error": error}, status=400)

        if field_str and tex_key:
            cached_result = (
                get_cached_results_from_request_field_and_tex_key(
                    request, tex_key, field_str))
            if cached_result:
                return JsonResponse(
                    cached_result,
                    status=400 if "compile_error" in cached_result else 200)

        data_url = None
        error = None

        try:
            _converter = tex_to_img_converter(
                compiler, tex_source, image_format, tex_key, **req_params)
        except Exception as e:
            from traceback import print_exc
            print_exc()
            tp, e, __ = sys.exc_info()
            error = "%s: %s" % (tp.__name__, str(e))
            return Response({"error": error}, status=400)

        qs = LatexImage.objects.filter(tex_key=_converter.tex_key)
        if qs.count():
            instance = qs[0]
            image_serializer = self.get_serializer(
                instance, fields=field_str)
            return Response(
                image_serializer.data, status=201
                if instance.data_url is not None else 400)

        try:
            data_url = _converter.get_converted_data_url()
        except Exception as e:
            if isinstance(e, LatexCompileError):
                error = "%s: %s" % (type(e).__name__, str(e))
            else:
                from traceback import print_exc
                print_exc()
                tp, e, __ = sys.exc_info()
                error = "%s: %s" % (tp.__name__, str(e))
                return Response({"error": error}, status=400)

        assert not all([data_url is None, error is None])

        data = {"tex_key": _converter.tex_key}
        if data_url is not None:
            data["data_url"] = data_url
        else:
            data["compile_error"] = error

        data["creator"] = self.request.user.pk

        image_serializer = self.get_serializer(data=data)

        if image_serializer.is_valid():
            instance = image_serializer.save()
            return Response(
                self.get_serializer(instance, fields=field_str).data,
                status=201 if data_url is not None else 400)
        return Response(image_serializer.errors, status=400)


class LatexImageList(
        CreateMixin, FieldsSerializerMixin, generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LatexImageSerializer

    def get_queryset(self):
        if not self.request.user.is_superuser:
            return LatexImage.objects.filter(creator=self.request.user)
        return LatexImage.objects.all()


class LatexImageCreate(
        CreateMixin, generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LatexImageSerializer


class LatexImageDetail(
        FieldsSerializerMixin, generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LatexImageSerializer

    lookup_field = "tex_key"

    def get_queryset(self):
        if not self.request.user.is_superuser:
            return LatexImage.objects.filter(creator=self.request.user)
        return LatexImage.objects.all()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        if instance.compile_error:
            return Response(serializer.data, status=400)
        else:
            return Response(serializer.data)

    def get(self, request, *args, **kwargs):
        tex_key = kwargs.get("tex_key")
        assert tex_key is not None
        fields_str = request.GET.getlist('fields')
        if len(fields_str) == 1:
            fields = fields_str[0].split(",")
            if len(fields) == 1:
                cached_result = (
                    get_cached_results_from_request_field_and_tex_key(
                        request, tex_key, fields[0]))
                if cached_result is not None:
                    return JsonResponse(
                        cached_result,
                        status=400 if "compile_error" in cached_result else 200)
        return self.retrieve(request, *args, **kwargs)
