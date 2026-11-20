from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from pointages.views import media_protege

admin.site.site_header = admin.site.site_title = settings.POINTAGE_MAX["NOM"]
admin.site.index_title = "Administration"

urlpatterns = [
    path('admin/', admin.site.urls),
    path('connexion/', auth_views.LoginView.as_view(template_name="pointages/connexion.html"), name="login"),
    path('deconnexion/', auth_views.LogoutView.as_view(), name="logout"),
    path('mot-de-passe/', auth_views.PasswordChangeView.as_view(
        template_name="pointages/mot_de_passe.html", success_url="/"), name="password_change"),
    path('media/<path:path>', media_protege, name="media"),
    path('', include("pointages.urls")),
]
