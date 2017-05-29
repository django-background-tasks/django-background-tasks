# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from datetime import datetime, timedelta
from importlib import import_module
from multiprocessing.pool import ThreadPool
import logging
import os
import sys

from compat import atomic
from django.utils import timezone
from django.utils.six import python_2_unicode_compatible

from background_task.exceptions import BackgroundTaskError
from background_task.models import Task
from background_task.settings import app_settings
from background_task import signals

logger = logging.getLogger(__name__)
_thread_pool = ThreadPool(processes=app_settings.BACKGROUND_TASK_ASYNC_THREADS)


def bg_runner(proxy_task, task=None, *args, **kwargs):
    """
    Executes the function attached to task. Used to enable threads.
    If a Task instance is provided, args and kwargs are ignored and retrieved from the Task itself.
    """
    signals.task_started.send(Task)
    try:
        func = getattr(proxy_task, 'task_function', None)
        if isinstance(task, Task):
            args, kwargs = task.params()
        else:
            task_name = getattr(proxy_task, 'name', None)
            task_queue = getattr(proxy_task, 'queue', None)
            task_qs = Task.objects.get_task(task_name=task_name, args=args, kwargs=kwargs)
            if task_queue:
                task_qs = task_qs.filter(queue=task_queue)
            if task_qs:
                task = task_qs[0]
        if func is None:
            raise BackgroundTaskError("Function is None, can't execute!")
        func(*args, **kwargs)

        if task:
            # task done, so can delete it
            task.increment_attempts()
            completed = task.create_completed_task()
            signals.task_successful.send(sender=task.__class__, task_id=task.id, completed_task=completed)
            task.create_repetition()
            task.delete()
            logger.info('Ran task and deleting %s', task)

    except Exception as ex:
        t, e, traceback = sys.exc_info()
        if task:
            logger.error('Rescheduling %s', task, exc_info=(t, e, traceback))
            signals.task_error.send(sender=ex.__class__, task=task)
            task.reschedule(t, e, traceback)
        del traceback
    signals.task_finished.send(Task)


class Tasks(object):
    def __init__(self):
        self._tasks = {}
        self._runner = DBTaskRunner()
        self._task_proxy_class = TaskProxy
        self._bg_runner = bg_runner

    def background(self, name=None, schedule=None, queue=None):
        '''
        decorator to turn a regular function into
        something that gets run asynchronously in
        the background, at a later time
        '''

        # see if used as simple decorator
        # where first arg is the function to be decorated
        fn = None
        if name and callable(name):
            fn = name
            name = None

        def _decorator(fn):
            _name = name
            if not _name:
                _name = '%s.%s' % (fn.__module__, fn.__name__)
            proxy = self._task_proxy_class(_name, fn, schedule, queue, self._runner)
            self._tasks[_name] = proxy
            return proxy
        if fn:
            return _decorator(fn)

        return _decorator

    def run_task(self, task_name, args=None, kwargs=None):
        # task_name can be either the name of a task or a Task instance.
        if isinstance(task_name, Task):
            task = task_name
            task_name = task.task_name
            # When we have a Task instance we do not need args and kwargs, but they are kept for backward compatibility
            args = []
            kwargs = {}
        else:
            task = None
        proxy_task = self._tasks[task_name]
        if app_settings.BACKGROUND_TASK_RUN_ASYNC:
            _thread_pool.apply_async(func=self._bg_runner, args=(proxy_task, task) + tuple(args), kwds=kwargs)
        else:
            self._bg_runner(proxy_task, task, *args, **kwargs)

    def run_next_task(self, queue=None):
        return self._runner.run_next_task(self, queue)


class TaskSchedule(object):
    SCHEDULE = 0
    RESCHEDULE_EXISTING = 1
    CHECK_EXISTING = 2

    def __init__(self, run_at=None, priority=None, action=None):
        self._run_at = run_at
        self._priority = priority
        self._action = action

    @classmethod
    def create(self, schedule):
        if isinstance(schedule, TaskSchedule):
            return schedule
        priority = None
        run_at = None
        action = None
        if schedule:
            if isinstance(schedule, (int, timedelta, datetime)):
                run_at = schedule
            else:
                run_at = schedule.get('run_at', None)
                priority = schedule.get('priority', None)
                action = schedule.get('action', None)
        return TaskSchedule(run_at=run_at, priority=priority, action=action)

    def merge(self, schedule):
        params = {}
        for name in ['run_at', 'priority', 'action']:
            attr_name = '_%s' % name
            value = getattr(self, attr_name, None)
            if value is None:
                params[name] = getattr(schedule, attr_name, None)
            else:
                params[name] = value
        return TaskSchedule(**params)

    @property
    def run_at(self):
        run_at = self._run_at or timezone.now()
        if isinstance(run_at, int):
            run_at = timezone.now() + timedelta(seconds=run_at)
        if isinstance(run_at, timedelta):
            run_at = timezone.now() + run_at
        return run_at

    @property
    def priority(self):
        return self._priority or 0

    @property
    def action(self):
        return self._action or TaskSchedule.SCHEDULE

    def __repr__(self):
        return 'TaskSchedule(run_at=%s, priority=%s)' % (self._run_at,
                                                         self._priority)

    def __eq__(self, other):
        return self._run_at == other._run_at \
           and self._priority == other._priority \
           and self._action == other._action


class DBTaskRunner(object):
    '''
    Encapsulate the model related logic in here, in case
    we want to support different queues in the future
    '''

    def __init__(self):
        self.worker_name = str(os.getpid())

    def schedule(self, task_name, args, kwargs, run_at=None,
                 priority=0, action=TaskSchedule.SCHEDULE, queue=None, verbose_name=None, creator=None,
                 repeat=None, repeat_until=None):
        '''Simply create a task object in the database'''

        task = Task.objects.new_task(task_name, args, kwargs,
                                     run_at, priority, queue, verbose_name, creator, repeat, repeat_until)

        if action != TaskSchedule.SCHEDULE:
            task_hash = task.task_hash
            now = timezone.now()
            unlocked = Task.objects.unlocked(now)
            existing = unlocked.filter(task_hash=task_hash)
            if queue:
                existing = existing.filter(queue=queue)
            if action == TaskSchedule.RESCHEDULE_EXISTING:
                updated = existing.update(run_at=run_at, priority=priority)
                if updated:
                    return
            elif action == TaskSchedule.CHECK_EXISTING:
                if existing.count():
                    return

        task.save()
        signals.task_created.send(sender=self.__class__, task=task)
        return task

    @atomic
    def get_task_to_run(self, tasks, queue=None):
        available_tasks = [task for task in Task.objects.find_available(queue)
                           if task.task_name in tasks._tasks][:5]
        for task in available_tasks:
            # try to lock task
            locked_task = task.lock(self.worker_name)
            if locked_task:
                return locked_task
        return None

    @atomic
    def run_task(self, tasks, task):
        logger.info('Running %s', task)
        tasks.run_task(task)

    @atomic
    def run_next_task(self, tasks, queue=None):
        # we need to commit to make sure
        # we can see new tasks as they arrive
        task = self.get_task_to_run(tasks, queue)
        # transaction.commit()
        if task:
            self.run_task(tasks, task)
            # transaction.commit()
            return True
        else:
            return False


@python_2_unicode_compatible
class TaskProxy(object):
    def __init__(self, name, task_function, schedule, queue, runner):
        self.name = name
        self.now = self.task_function = task_function
        self.runner = runner
        self.schedule = TaskSchedule.create(schedule)
        self.queue = queue

    def __call__(self, *args, **kwargs):
        schedule = kwargs.pop('schedule', None)
        schedule = TaskSchedule.create(schedule).merge(self.schedule)
        run_at = schedule.run_at
        priority = kwargs.pop('priority', schedule.priority)
        action = schedule.action
        queue = kwargs.pop('queue', self.queue)
        verbose_name = kwargs.pop('verbose_name', None)
        creator = kwargs.pop('creator', None)
        repeat = kwargs.pop('repeat', None)
        repeat_until = kwargs.pop('repeat_until', None)
        return self.runner.schedule(self.name, args, kwargs, run_at, priority, action, queue,
                                    verbose_name, creator, repeat, repeat_until)

    def __str__(self):
        return 'TaskProxy(%s)' % self.name

tasks = Tasks()


def autodiscover():
    """
    Autodiscover tasks.py files in much the same way as admin app
    """
    import imp
    from django.conf import settings

    for app in settings.INSTALLED_APPS:
        try:
            app_path = import_module(app).__path__
        except (AttributeError, ImportError):
            continue
        try:
            imp.find_module('tasks', app_path)
        except ImportError:
            continue

        import_module("%s.tasks" % app)
