from django.urls import path
from . import views

app_name = 'landing'

urlpatterns = [
    path('', views.LandingView.as_view(), name='home'),
    path('catalogo/', views.CatalogView.as_view(), name='catalog'),
]
