from celery import Celery
from celery.schedules import crontab
from django.conf import settings
import os

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'investment_system.settings')

app = Celery('investment_system')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()


# Celery Beat Schedule for Investment Tasks
app.conf.beat_schedule = {
    # Daily ROI crediting task - runs every day at 00:00 UTC
    'credit-daily-roi': {
        'task': 'app.investment.tasks.credit_roi_task',
        'schedule': crontab(hour=0, minute=0),
        'args': (),
    },
    
    # Weekly ROI crediting task - runs every Monday at 00:00 UTC
    'credit-weekly-roi': {
        'task': 'app.investment.tasks.credit_roi_task',
        'schedule': crontab(day_of_week=1, hour=0, minute=0),
        'args': (),
    },
    
    # Monthly ROI crediting task - runs on the 1st of every month at 00:00 UTC
    'credit-monthly-roi': {
        'task': 'app.investment.tasks.credit_roi_task',
        'schedule': crontab(day_of_month=1, hour=0, minute=0),
        'args': (),
    },
    
    # Process completed investments - runs daily at 01:00 UTC
    'process-completed-investments': {
        'task': 'app.investment.tasks.process_completed_investments',
        'schedule': crontab(hour=1, minute=0),
        'args': (),
    },
    
    # Cleanup old breakdown requests - runs weekly on Sunday at 02:00 UTC
    'cleanup-old-breakdown-requests': {
        'task': 'app.investment.tasks.cleanup_old_breakdown_requests',
        'schedule': crontab(day_of_week=0, hour=2, minute=0),
        'args': (),
    },
    
    # Investment system health check - runs daily at 03:00 UTC
    'investment-health-check': {
        'task': 'app.investment.tasks.investment_health_check',
        'schedule': crontab(hour=3, minute=0),
        'args': (),
    },
}


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')


# Optional: Configure Celery to use Redis as result backend
if hasattr(settings, 'CELERY_RESULT_BACKEND'):
    app.conf.result_backend = settings.CELERY_RESULT_BACKEND

# Optional: Configure Celery to use Redis as message broker
if hasattr(settings, 'CELERY_BROKER_URL'):
    app.conf.broker_url = settings.CELERY_BROKER_URL

# Configure Celery to handle timezone-aware datetimes
app.conf.enable_utc = True
app.conf.timezone = 'UTC'

# Configure task routing
app.conf.task_routes = {
    'app.investment.tasks.*': {'queue': 'investment'},
}

# Configure task serialization
app.conf.task_serializer = 'json'
app.conf.result_serializer = 'json'
app.conf.accept_content = ['json']

# Configure task execution
app.conf.task_always_eager = False  # Set to True for testing
app.conf.task_eager_propagates = True

# Configure worker settings
app.conf.worker_prefetch_multiplier = 1
app.conf.worker_max_tasks_per_child = 1000

# Configure task retry settings
app.conf.task_acks_late = True
app.conf.task_reject_on_worker_lost = True
