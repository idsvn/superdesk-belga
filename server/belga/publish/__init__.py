from superdesk.celery_app import celery

from . import belga_newsml_1_2
from .auto_publish import AutoPublishService


@celery.task()
def autopublish():
    AutoPublishService().run()
