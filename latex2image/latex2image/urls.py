"""latex2image URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.conf.urls import url, include
from latex import views
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('admin/', admin.site.urls),
    url(r"^$", views.request_get_data_url_from_latex_form_request, name="home"),
    url(r"^api/list$", views.LatexImageList.as_view(), name="list"),
    url(r"^api/detail/(?P<tex_key>[a-zA-Z0-9_]+)$", views.LatexImageDetail.as_view(), name="detail"),
    url(r"^api/create$", views.LatexImageCreate.as_view(), name="create"),
    path('api-auth/', include('rest_framework.urls')),
    url(r'^login/$', auth_views.LoginView.as_view(
        template_name='registration/login.html', form_class=views.AuthenticationForm,
        extra_context={"form_description": "Login"}), name='login'),
    url(r'^logout/$', auth_views.LogoutView.as_view(template_name='registration/logged_out.html'), name='logout'),
    url(r'^profile/$', views.user_profile, name='profile'),
]

# For generated image files
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
