from django.contrib import admin

from .models import JobRun


@admin.register(JobRun)
class JobRunAdmin(admin.ModelAdmin):
    list_display = ["job_name", "status", "started_at", "finished_at", "triggered_by"]
    list_filter = ["job_name", "status"]
