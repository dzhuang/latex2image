from django.contrib import admin
from django import forms
from django.utils.safestring import mark_safe
from django.contrib.admin import SimpleListFilter
from django.utils.translation import ugettext_lazy as _

from latex.models import LatexImage


class LatexImageAdminForm(forms.ModelForm):
    class Meta:
        model = LatexImage
        exclude = ()


class HasCompileErrorFilter(SimpleListFilter):
    title = _('has compile error')
    parameter_name = 'compile_error'

    def lookups(self, request, model_admin):
        return(
            ('y', _('Yes')),
            ('n', _('No')))

    def queryset(self, request, queryset):
        if self.value() == 'y':
            return queryset.filter(compile_error__isnull=False)
        else:
            return queryset.filter(compile_error__isnull=True)


class LatexImageAdmin(admin.ModelAdmin):
    _readonly_fields = ["data_url", "compile_error"]
    readonly_fields = ["data_url_image"]
    list_display = (
            "id",
            "tex_key",
            "creation_time",
            "data_url_image",
            "creator",
    )
    list_filter = ("creation_time", "creator", HasCompileErrorFilter)
    search_fields = (
            "tex_key",
            "image",
            "compile_error")

    form = LatexImageAdminForm
    save_on_top = True

    def get_form(self, *args, **kwargs):
        form = super(LatexImageAdmin, self).get_form(*args, **kwargs)

        for field_name in self._readonly_fields:
            form.base_fields[field_name].disabled = True

        return form

    @staticmethod
    def data_url_image(obj):
        if obj.data_url:
            return mark_safe(
                '<img style="max-width: 200px;" src="{url}"/>'.format(
                    url=obj.data_url,
                )
            )
        return None


admin.site.register(LatexImage, LatexImageAdmin)
