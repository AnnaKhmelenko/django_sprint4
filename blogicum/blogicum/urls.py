from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import CreateView
from django.urls import reverse_lazy
from blog.forms import UserEditForm

from blogicum import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('blog.urls', namespace='blog')),
    path('pages/', include('pages.urls', namespace='pages')),
    path('auth/', include('django.contrib.auth.urls')),
    path(
        'auth/registration/',
        CreateView.as_view(
            form_class=UserEditForm,
            template_name='registration/registration_form.html',
            success_url=reverse_lazy('login')
        ),
        name='registration'),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )

handler404 = 'pages.views.page_not_found'
handler500 = 'pages.views.server_error'
