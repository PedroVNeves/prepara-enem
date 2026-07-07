from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View

from irt.services import recalibrate_tri
from redacao.services import process_pending_essay_submissions

from .jobs import JobAlreadyRunning, run_job
from .models import JobRun

JOBS = {
    "process_essay_queue": process_pending_essay_submissions,
    "recalibrate_tri": recalibrate_tri,
}


@method_decorator(staff_member_required, name="dispatch")
class TriggerJobView(View):
    template_name = "ops/trigger_job.html"

    def get(self, request):
        runs = JobRun.objects.all()[:20]
        return render(request, self.template_name, {"jobs": JOBS.keys(), "runs": runs})

    def post(self, request):
        job_name = request.POST["job_name"]
        job_fn = JOBS.get(job_name)
        if job_fn:
            try:
                with run_job(job_name, triggered_by="manual") as summary:
                    summary.update(job_fn())
            except JobAlreadyRunning:
                pass
        return redirect("ops:trigger_job")
