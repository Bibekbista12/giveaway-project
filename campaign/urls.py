from django.urls import path
from .views import SpinView, RegisterView, registration_success

urlpatterns = [
    path("spin/", SpinView.as_view(), name="spin"),
    path("register/<uuid:spin_session_id>/", RegisterView.as_view(), name="register"),
    path("registration-success/", registration_success, name="registration_success"),
]