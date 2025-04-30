# -*- coding: utf-8 -*-
from django.contrib import admin
from background_task.models import Task
from background_task.models import CompletedTask


def inc_priority(modeladmin, request, queryset):
    for obj in queryset:
        obj.priority += 1
        obj.save()
inc_priority.short_description = "priority += 1"

def dec_priority(modeladmin, request, queryset):
    for obj in queryset:
        obj.priority -= 1
        obj.save()
dec_priority.short_description = "priority -= 1"


class TaskMixin:
    """Modify a few properties of background tasks displayed in admin."""

    def no_errors(self, obj):
        """Replace background_task's "has_error".

        Make Django's red/green boolean icons less confusing
        in the context of "there's an error during task run".
        """
        return not bool(obj.last_error)

    no_errors.boolean = True


class TaskAdmin(TaskMixin, admin.ModelAdmin):
    date_hierarchy = 'run_at'
    list_display = [
        'run_at',
        'task_name',
        'task_params',
        'creator',
        'attempts',
        'no_errors',
        'locked_by',
        'locked_by_pid_running',
    ]
    list_filter = (
        'task_name',
        'run_at',
        'failed_at',
        'locked_at',
        'attempts',
        'creator_content_type',
    )
    search_fields = ['task_name', 'task_params', 'last_error', 'verbose_name']


admin.site.register(Task, TaskAdmin)
admin.site.register(CompletedTask, TaskAdmin)
