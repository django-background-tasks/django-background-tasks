# -*- coding: utf-8 -*-
import django
__version__ = '1.2.5'

if django.VERSION < (3, 2):
    default_app_config = 'background_task.apps.BackgroundTasksAppConfig'
    
def background(*arg, **kw):
    from background_task.tasks import tasks
    return tasks.background(*arg, **kw)
