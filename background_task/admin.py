# -*- coding: utf-8 -*-
from django.contrib import admin
from background_task.models_completed import CompletedTask

from background_task.models import Task


class TaskAdmin(admin.ModelAdmin):
    display_filter = ['task_name']
    list_display = ['task_name', 'task_params', 'run_at', 'priority', 'attempts', 'has_error', 'locked_by', 'locked_by_pid_running', ]


class CompletedTaskAdmin(admin.ModelAdmin):
    display_filter = ['task_name']
    list_display = ['task_name', 'task_params', 'run_at', 'priority', 'attempts', 'has_error', 'locked_by', 'locked_by_pid_running', ]


admin.site.register(Task, TaskAdmin)
admin.site.register(CompletedTask, CompletedTaskAdmin)
