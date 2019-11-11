# -*- coding: utf-8 -*-
import logging
import sys

from django import VERSION
from django.core.management.base import BaseCommand

from background_task.tasks import process_tasks, tasks

logger = logging.getLogger(__name__)


def _configure_log_std():
    class StdOutWrapper(object):
        def write(self, s):
            logger.info(s)

    class StdErrWrapper(object):
        def write(self, s):
            logger.error(s)
    sys.stdout = StdOutWrapper()
    sys.stderr = StdErrWrapper()


class Command(BaseCommand):
    help = 'Run tasks that are scheduled to run on the queue'

    # Command options are specified in an abstract way to enable Django < 1.8 compatibility
    OPTIONS = (
        (('--duration', ), {
            'action': 'store',
            'dest': 'duration',
            'type': int,
            'default': 0,
            'help': 'Run task for this many seconds (0 or less to run forever) - default is 0',
        }),
        (('--sleep', ), {
            'action': 'store',
            'dest': 'sleep',
            'type': float,
            'default': 5.0,
            'help': 'Sleep for this many seconds before checking for new tasks (if none were found) - default is 5',
        }),
        (('--queue', ), {
            'action': 'store',
            'dest': 'queue',
            'help': 'Only process tasks on this named queue',
        }),
        (('--log-std', ), {
            'action': 'store_true',
            'dest': 'log_std',
            'help': 'Redirect stdout and stderr to the logging system',
        }),

    )

    if VERSION < (1, 8):
        from optparse import make_option
        option_list = BaseCommand.option_list + tuple([make_option(*args, **kwargs) for args, kwargs in OPTIONS])

    # Used in Django >= 1.8
    def add_arguments(self, parser):
        for (args, kwargs) in self.OPTIONS:
            parser.add_argument(*args, **kwargs)

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self._tasks = tasks

    def handle(self, *args, **options):
        duration = options.pop('duration', 0)
        sleep = options.pop('sleep', 5.0)
        queue = options.pop('queue', None)
        log_std = options.pop('log_std', False)

        if log_std:
            _configure_log_std()

        process_tasks(queue, sleep, duration)
