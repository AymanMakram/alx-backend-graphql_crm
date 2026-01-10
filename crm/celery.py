import os
from celery import Celery

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm.settings')

app = Celery('crm')

# Use Redis as the broker (as requested)
app.conf.broker_url = 'redis://localhost:6379/0'

# Load task modules from all registered Django app configs.
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Optional: a simple debug task to confirm worker is running
@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
