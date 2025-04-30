# -*- coding: utf-8 -*-
__version__ = '1.2.8'


def background(*arg, **kw):
    from background_task.tasks import tasks
    return tasks.background(*arg, **kw)
