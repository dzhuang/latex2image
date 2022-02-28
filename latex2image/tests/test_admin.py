from random import randint

from django.contrib.admin import site
from django.test import RequestFactory, TestCase
from django.urls import reverse
from tests import factories
from tests.base_test_mixins import L2ITestMixinBase

from latex import models
from latex.admin import LatexImageAdmin


class AdminTest(L2ITestMixinBase, TestCase):
    def setUp(self):  # noqa
        super().setUp()

        self.n_images = randint(10, 20)
        self.images = factories.LatexImageFactory.create_batch(size=self.n_images)
        self.n_errors = randint(5, 10)
        self.error_instances = (
            factories.LatexImageErrorFactory.create_batch(size=self.n_errors))
        self.client.force_login(self.superuser)

    @classmethod
    def get_admin_change_list_view_url(cls, app_name, model_name):
        return reverse("admin:%s_%s_changelist" % (app_name, model_name))

    @classmethod
    def get_admin_change_view_url(cls, app_name, model_name, args=None):
        if args is None:
            args = []
        return reverse("admin:%s_%s_change" % (app_name, model_name), args=args)

    @classmethod
    def get_admin_add_view_url(cls, app_name, model_name, args=None):
        if args is None:
            args = []
        return reverse("admin:%s_%s_add" % (app_name, model_name), args=args)

    def get_admin_form_fields(self, response):
        """
        Return a list of AdminFields for the AdminForm in the response.
        """
        admin_form = response.context['adminform']
        fieldsets = list(admin_form)

        field_lines = []
        for fieldset in fieldsets:
            field_lines += list(fieldset)

        fields = []
        for field_line in field_lines:
            fields += list(field_line)

        return fields

    def get_admin_form_fields_names(self, response):
        return [f.field.name for f in self.get_admin_form_fields(response)]

    def get_changelist(self, request, model=None, model_admin=None):
        model = model or models.LatexImage
        model_admin = model_admin or LatexImageAdmin(models.LatexImage, site)
        from django.contrib.admin.views.main import ChangeList
        return ChangeList(
            request, model, model_admin.list_display,
            model_admin.list_display_links, model_admin.get_list_filter(request),
            model_admin.date_hierarchy, model_admin.search_fields,
            model_admin.list_select_related, model_admin.list_per_page,
            model_admin.list_max_show_all, model_admin.list_editable,
            model_admin=model_admin,
            sortable_by=model_admin.sortable_by
        )

    def get_filterspec_list(self, request, changelist=None, model=None,
                            model_admin=None):
        model = model or models.LatexImage
        model_admin = model_admin or LatexImageAdmin(models.LatexImage, site)
        if changelist is None:
            assert request and model and model_admin
            changelist = self.get_changelist(request, model, model_admin)

        filterspecs = changelist.get_filters(request)[0]
        filterspec_list = []
        for filterspec in filterspecs:
            choices = tuple(c['display'] for c in filterspec.choices(changelist))
            filterspec_list.append(choices)

        return filterspec_list

    def get_admin_l2i_change_list_view_url(self, model_name=None):
        model_name = model_name or models.LatexImage.__name__
        return self.get_admin_change_list_view_url(
            app_name="latex", model_name=model_name.lower())

    def get_admin_l2i_add_view_url(self, model_name=None):
        model_name = model_name or models.LatexImage.__name__
        return self.get_admin_add_view_url(
            app_name="latex", model_name=model_name.lower())

    def get_admin_l2i_change_view_url(self, args, model_name=None):
        model_name = model_name or models.LatexImage.__name__
        return self.get_admin_change_view_url(
            app_name="latex", model_name=model_name.lower(), args=args)

    def test_list_view(self):
        resp = self.client.get(self.get_admin_l2i_change_list_view_url())
        self.assertEqual(resp.status_code, 200)

    def test_list_view_when_image_file_deleted(self):
        import os
        os.remove(self.images[0].image.path)
        resp = self.client.get(self.get_admin_l2i_change_list_view_url())
        self.assertEqual(resp.status_code, 200)

    def test_add_view(self):
        resp = self.client.get(self.get_admin_l2i_add_view_url())
        self.assertEqual(resp.status_code, 200)

    def test_change_view(self):
        resp = self.client.get(
            self.get_admin_l2i_change_view_url(
                args=[self.images[0].pk]))
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get(
            self.get_admin_l2i_change_view_url(
                args=[self.error_instances[0].pk]))
        self.assertEqual(resp.status_code, 200)

    def test_change_view_when_image_file_deleted(self):
        import os
        pk = self.images[0].pk
        os.remove(self.images[0].image.path)
        resp = self.client.get(
            self.get_admin_l2i_change_view_url(
                args=[pk]))
        self.assertEqual(resp.status_code, 200)

    def test_filter_spec_no_filter(self):
        rf = RequestFactory()
        request = rf.get(
            self.get_admin_l2i_change_list_view_url(), {})
        request.user = self.superuser
        changelist = self.get_changelist(request)

        queryset = changelist.get_queryset(request)

        self.assertEqual(queryset.count(), self.n_images + self.n_errors)

    def test_filter_spec_no_errors(self):
        rf = RequestFactory()
        request = rf.get(
            self.get_admin_l2i_change_list_view_url(), {"has_compile_error": "n"})
        request.user = self.superuser
        changelist = self.get_changelist(request)

        queryset = changelist.get_queryset(request)

        self.assertEqual(queryset.count(), self.n_images)

    def test_filter_spec_has_errors(self):
        rf = RequestFactory()
        request = rf.get(
            self.get_admin_l2i_change_list_view_url(), {"has_compile_error": "y"})
        request.user = self.superuser
        changelist = self.get_changelist(request)

        queryset = changelist.get_queryset(request)
        self.assertEqual(queryset.count(), self.n_errors)
