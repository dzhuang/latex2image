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


from django.conf import settings
from django.conf.urls import include
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, re_path
from django.utils.translation import gettext_lazy as _

from latex import api, auth, views

admin.site.site_header = _("LaTeX2Image Admin")
admin.site.site_title = _("LaTeX2Image Admin")

urlpatterns = [
    path('admin/', admin.site.urls),
    re_path("$", views.request_get_data_url_from_latex_form_request, name="home"),
    re_path('login/$', auth_views.LoginView.as_view(
        template_name='registration/login.html', form_class=auth.AuthenticationForm,
        extra_context={"form_description": "Login"}), name='login'),
    re_path(r'^logout/$', auth_views.LogoutView.as_view(
        template_name='registration/logged_out.html'), name='logout'),
    re_path(r'^profile/$', auth.user_profile, name='profile'),

    path('api-auth/', include('rest_framework.urls')),
    re_path(r"^api/create/$", api.LatexImageCreate.as_view(), name="create"),
    re_path(r"^api/list/$", api.LatexImageList.as_view(), name="list"),
    re_path(r"^api/detail/(?P<tex_key>[a-zA-Z0-9_]+)$",
            api.LatexImageDetail.as_view(),
            name="detail"),
]

# For generated image files
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
