# -*- coding: utf-8 -*-
__version__ = '1.1.7'

default_app_config = 'background_task.apps.BackgroundTasksAppConfig'

def background(*arg, **kw):
    from background_task.tasks import tasks
    return tasks.background(*arg, **kw)
