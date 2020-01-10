# -*- coding: utf-8 -*-
import multiprocessing

from django.conf import settings

try:
    cpu_count = multiprocessing.cpu_count()
except Exception:
    cpu_count = 1


class AppSettings(object):
    """
    """
    @property
    def MAX_ATTEMPTS(self):
        """Control how many times a task will be attempted."""
        return getattr(settings, 'MAX_ATTEMPTS', 25)

    @property
    def BACKGROUND_TASK_MAX_ATTEMPTS(self):
        """Control how many times a task will be attempted."""
        return self.MAX_ATTEMPTS

    @property
    def BACKGROUND_TASK_DELAY_BETWEEN_ATTEMPTS(self):
        """
        Control the delay between each attempt (expressed in seconds). It can be either:

        * an integer;
        * a callable that receive one argument - the number of attempts done after the current run.

        Default value: lambda attempts: (attempts ** 4) + 5
        """
        return getattr(settings, 'BACKGROUND_TASK_DELAY_BETWEEN_ATTEMPTS', lambda attempts: (attempts ** 4) + 5)

    @property
    def MAX_RUN_TIME(self):
        """Maximum possible task run time, after which tasks will be unlocked and tried again."""
        return getattr(settings, 'MAX_RUN_TIME', 3600)

    @property
    def BACKGROUND_TASK_MAX_RUN_TIME(self):
        """Maximum possible task run time, after which tasks will be unlocked and tried again."""
        return self.MAX_RUN_TIME

    @property
    def BACKGROUND_TASK_RUN_ASYNC(self):
        """Control if tasks will run asynchronous in a ThreadPool."""
        return getattr(settings, 'BACKGROUND_TASK_RUN_ASYNC', False)

    @property
    def BACKGROUND_TASK_ASYNC_THREADS(self):
        """Specify number of concurrent threads."""
        return getattr(settings, 'BACKGROUND_TASK_ASYNC_THREADS', cpu_count)

    @property
    def BACKGROUND_TASK_PRIORITY_ORDERING(self):
        """
        Control the ordering of tasks in the queue.
        Choose either `DESC` or `ASC`.

        https://en.m.wikipedia.org/wiki/Nice_(Unix)
        A niceness of −20 is the highest priority and 19 is the lowest priority. The default niceness for processes is inherited from its parent process and is usually 0.
        """
        order = getattr(settings, 'BACKGROUND_TASK_PRIORITY_ORDERING', 'DESC')
        if order == 'ASC':
            prefix = ''
        else:
            prefix = '-'
        return prefix


app_settings = AppSettings()
