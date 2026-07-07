from django.urls import path

from . import views

app_name = "ops"

urlpatterns = [
    path("jobs/", views.TriggerJobView.as_view(), name="trigger_job"),
]
