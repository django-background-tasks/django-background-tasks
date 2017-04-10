# Django Background Tasks

[![Build Status](https://travis-ci.org/arteria/django-background-tasks.svg?branch=master)](https://travis-ci.org/arteria/django-background-tasks)
[![Documentation Status](https://readthedocs.org/projects/django-background-tasks/badge/?version=latest)](http://django-background-tasks.readthedocs.io/en/latest/?badge=latest)
[![PyPI](https://img.shields.io/pypi/v/django-background-tasks.svg)](https://pypi.python.org/pypi/django-background-tasks)


Django Background Task is a databased-backed work queue for Django, loosely based around [Ruby's DelayedJob](https://github.com/tobi/delayed_job) library. This project was adopted and adapted from [lilspikey](https://github.com/lilspikey/) django-background-task.

To avoid conflicts on PyPI we renamed it to django-background-tasks (plural). For an easy upgrade from django-background-task to django-background-tasks, the internal module structure were left untouched.

In Django Background Task, all tasks are implemented as functions (or any other callable).

There are two parts to using background tasks:

* creating the task functions and registering them with the scheduler
* setup a cron task (or long running process) to execute the tasks


## Docs
See http://django-background-tasks.readthedocs.io/en/latest/.
