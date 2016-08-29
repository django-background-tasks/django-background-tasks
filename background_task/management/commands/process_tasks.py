from django.core.management.base import BaseCommand
import time
import logging
import sys
from random import choice
from background_task.tasks import tasks, autodiscover

class Command(BaseCommand):
    LOG_LEVELS = ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG']
    
    help = 'Run tasks that are scheduled to run on the queue'
    def add_arguments(self, parser):
        parser.add_argument('--duration',
                action='store',
                dest='duration',
                type=int,
                default=0,
                help='Run task for this many seconds (0 or less to run forever) - default is 0')
        parser.add_argument('--sleep',
                action='store',
                dest='sleep',
                type=float,
                default=5.0,
                help='Sleep for this many seconds before checking for new tasks (if none were found) - default is 5')
        parser.add_argument('--queue',
                action='store',
                dest='queue',
                help='Only process tasks on this named queue')
        parser.add_argument('--log-file',
                action='store',
                dest='log_file',
                help='Log file destination')
        parser.add_argument('--log-std',
                action='store_true',
                dest='log_std',
                help='Redirect stdout and stderr to the logging system')       
        parser.add_argument('--log-level',
                action='store',
                type=choice,
                choices=self.LOG_LEVELS,
                dest='log_level',
                help='Set logging level (%s)' % ', '.join(self.LOG_LEVELS)
            )

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self._tasks = tasks

    
    def _configure_logging(self, log_level, log_file, log_std):

        if log_level:
            log_level = getattr(logging, log_level)
        
        config = {}
        if log_level:
            config['level'] = log_level
        if log_file:
            config['filename'] = log_file
        
        if config:
            logging.basicConfig(**config)

        if log_std:
            class StdOutWrapper(object):
                def write(self, s):
                    logging.info(s)
            class StdErrWrapper(object):
                def write(self, s):
                    logging.error(s)
            sys.stdout = StdOutWrapper()
            sys.stderr = StdErrWrapper()

    
    def handle(self, *args, **options):
        log_level = options.pop('log_level', None)
        log_file = options.pop('log_file', None)
        log_std = options.pop('log_std', False)
        duration = options.pop('duration', 0)
        sleep = options.pop('sleep', 5.0)
        queue = options.pop('queue', None)
        
        self._configure_logging(log_level, log_file, log_std)
        
        autodiscover()
        
        start_time = time.time()
        
        while (duration <= 0) or (time.time() - start_time) <= duration:
            if not self._tasks.run_next_task(queue):
                logging.debug('waiting for tasks')
                time.sleep(sleep)
