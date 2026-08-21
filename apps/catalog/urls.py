from django.urls import path
from .views.catalog import CatalogView, ProductDetailView

app_name = "catalog"

urlpatterns = [
    path("", CatalogView.as_view(), name="home"),
    path("productos/<slug:slug>/", ProductDetailView.as_view(), name="product_detail"),
]
