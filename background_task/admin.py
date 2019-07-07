# -*- coding: utf-8 -*-
from django.contrib import admin

from background_task.models import Task, CompletedTask
from background_task.settings import app_settings


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

if app_settings.BACKGROUND_TASK_BOOLEAN_AS_TEXT:
    def boolean_display(b):
        if b is None:
            return
        elif b:
            return 'Yes'
        else:
            return 'No'

    def has_error(task):
        return boolean_display(task.has_error())

    def locked_by_pid_running(task):
        return boolean_display(task.locked_by_pid_running())
else:
    def has_error(task):
        return task.has_error()
    has_error.boolean = True

    def locked_by_pid_running(task):
        return task.locked_by_pid_running()
    locked_by_pid_running.boolean = True

class TaskAdmin(admin.ModelAdmin):
    display_filter = ['task_name']
    search_fields = ['task_name', 'task_params', ]
    list_display = ['task_name', 'task_params', 'run_at', 'priority', 'attempts', has_error, 'locked_by',
                    locked_by_pid_running, ]
    actions = [inc_priority, dec_priority]

class CompletedTaskAdmin(admin.ModelAdmin):
    display_filter = ['task_name']
    search_fields = ['task_name', 'task_params', ]
    list_display = ['task_name', 'task_params', 'run_at', 'priority', 'attempts', has_error, 'locked_by',
                    locked_by_pid_running, ]

admin.site.register(Task, TaskAdmin)
admin.site.register(CompletedTask, CompletedTaskAdmin)
