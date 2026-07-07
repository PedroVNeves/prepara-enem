"""APScheduler rodando dentro do próprio processo Django — dispensa cron
externo já que o host (Render Starter) não dorme mais. Duas cadências:
fila de redação (curta, feature user-facing) e recalibração TRI (semanal,
processo de fundo). Cada execução reaproveita ops.jobs.run_job/JobRun para
auditoria e trava contra execução concorrente duplicada."""

import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler

from .jobs import JobAlreadyRunning, run_job

logger = logging.getLogger(__name__)

_scheduler = None


def _run_essay_queue():
    from redacao.services import process_pending_essay_submissions

    try:
        with run_job("process_essay_queue", triggered_by="scheduler") as summary:
            summary.update(process_pending_essay_submissions())
    except JobAlreadyRunning:
        logger.info("process_essay_queue já em execução, pulando este tick")


def _run_tri_recalibration():
    from irt.services import recalibrate_tri  # lazy import (girth ~110MB)

    try:
        with run_job("recalibrate_tri", triggered_by="scheduler") as summary:
            summary.update(recalibrate_tri())
    except JobAlreadyRunning:
        logger.info("recalibrate_tri já em execução, pulando este tick")


def start():
    global _scheduler
    if _scheduler is not None:
        return

    # Sob `runserver` com autoreload (padrão), o AppConfig.ready() roda duas
    # vezes (processo pai do watcher + processo filho real) — só inicia no
    # filho, identificado por RUN_MAIN=true.
    if "RUN_MAIN" in os.environ and os.environ.get("RUN_MAIN") != "true":
        return

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        _run_essay_queue, "interval", minutes=5, id="process_essay_queue", replace_existing=True
    )
    _scheduler.add_job(
        _run_tri_recalibration,
        "cron",
        day_of_week="sun",
        hour=3,
        id="recalibrate_tri",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("APScheduler iniciado: process_essay_queue (5min), recalibrate_tri (semanal)")
