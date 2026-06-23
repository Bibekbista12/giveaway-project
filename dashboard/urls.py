from django.urls import path
from .views import stats_view, export_csv

urlpatterns = [
    path("", stats_view, name="dashboard_stats"),
    path("export/", export_csv, name="dashboard_export"),
]