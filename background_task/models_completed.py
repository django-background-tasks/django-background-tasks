# -*- coding: utf-8 -*-
import os

from compat import python_2_unicode_compatible
from compat.models import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from django.db import models
from django.utils import timezone

from background_task.models import Task


class CompletedTaskQuerySet(models.QuerySet):

    def created_by(self, creator):
        """
        :return: A CompletedTask queryset filtered by creator
        """
        content_type = ContentType.objects.get_for_model(creator)
        return self.filter(
            creator_content_type=content_type,
            creator_object_id=creator.id,
        )

    def failed(self, within=None):
        """
        :param within: A timedelta object
        :return: A queryset of CompletedTasks that failed within the given timeframe (e.g. less than 1h ago)
        """
        qs = self.filter(
            failed_at__isnull=False,
        )
        if within:
            time_limit = timezone.now() - within
            qs = qs.filter(failed_at__gt=time_limit)
        return qs

    def succeeded(self, within=None):
        """
        :param within: A timedelta object
        :return: A queryset of CompletedTasks that completed successfully within the given timeframe
        (e.g. less than 1h ago)
        """
        qs = self.filter(
            failed_at__isnull=True,
        )
        if within:
            time_limit = timezone.now() - within
            qs = qs.filter(run_at__gt=time_limit)
        return qs


@python_2_unicode_compatible
class CompletedTask(models.Model):
    # the "name" of the task/function to be run
    task_name = models.CharField(max_length=255, db_index=True)
    # the json encoded parameters to pass to the task
    task_params = models.TextField()
    # a sha1 hash of the name and params, to lookup already scheduled tasks
    task_hash = models.CharField(max_length=40, db_index=True)

    verbose_name = models.CharField(max_length=255, null=True, blank=True)

    # what priority the task has
    priority = models.IntegerField(default=0, db_index=True)
    # when the task should be run
    run_at = models.DateTimeField(db_index=True)

    repeat = models.BigIntegerField(choices=Task.REPEAT_CHOICES, default=Task.NEVER)
    repeat_until = models.DateTimeField(null=True, blank=True)

    # the "name" of the queue this is to be run on
    queue = models.CharField(max_length=255, db_index=True,
                             null=True, blank=True)

    # how many times the task has been tried
    attempts = models.IntegerField(default=0, db_index=True)
    # when the task last failed
    failed_at = models.DateTimeField(db_index=True, null=True, blank=True)
    # details of the error that occurred
    last_error = models.TextField(blank=True)

    # details of who's trying to run the task at the moment
    locked_by = models.CharField(max_length=64, db_index=True,
                                 null=True, blank=True)
    locked_at = models.DateTimeField(db_index=True, null=True, blank=True)

    creator_content_type = models.ForeignKey(
        ContentType, null=True, blank=True,
        related_name='completed_background_task', on_delete=models.CASCADE
    )
    creator_object_id = models.PositiveIntegerField(null=True, blank=True)
    creator = GenericForeignKey('creator_content_type', 'creator_object_id')

    objects = CompletedTaskQuerySet.as_manager()

    def locked_by_pid_running(self):
        """
        Check if the locked_by process is still running.
        """
        try:
            # won't kill the process. kill is a bad named system call
            os.kill(int(self.locked_by), 0)
            return True
        except:
            return False
    locked_by_pid_running.boolean = True

    def has_error(self):
        """
        Check if the last_error field is empty.
        """
        return bool(self.last_error)
    has_error.boolean = True

    def __str__(self):
        return u'{} - {}'.format(
            self.verbose_name or self.task_name,
            self.run_at,
        )
