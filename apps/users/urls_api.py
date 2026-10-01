from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

# El UserViewSet se registra en config/api_router.py bajo /api/v1/usuarios/.
# Aquí solo viven los endpoints de token para evitar un registro duplicado.
urlpatterns = [
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]