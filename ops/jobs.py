"""Helper compartilhado por management commands e pela view de disparo manual
(TriggerJobView): registra um JobRun e impede execução concorrente duplicada
do mesmo job."""

from contextlib import contextmanager

from django.utils import timezone

from .models import JobRun, StatusJobRun


class JobAlreadyRunning(Exception):
    pass


@contextmanager
def run_job(job_name, triggered_by="manual"):
    if JobRun.objects.filter(job_name=job_name, status=StatusJobRun.RUNNING).exists():
        raise JobAlreadyRunning(f"Job '{job_name}' já está em execução.")

    job_run = JobRun.objects.create(job_name=job_name, triggered_by=triggered_by)
    summary = {}
    try:
        yield summary
        job_run.status = StatusJobRun.SUCCESS
        job_run.summary = str(summary)
    except Exception as exc:
        job_run.status = StatusJobRun.FAILED
        job_run.summary = str(exc)
        raise
    finally:
        job_run.finished_at = timezone.now()
        job_run.save(update_fields=["status", "summary", "finished_at"])
