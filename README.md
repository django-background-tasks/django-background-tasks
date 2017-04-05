# Django Background Tasks

[![Build Status](https://travis-ci.org/arteria/django-background-tasks.svg?branch=master)](https://travis-ci.org/arteria/django-background-tasks)
[![Documentation Status](https://readthedocs.org/projects/django-background-tasks/badge/?version=latest)](http://django-background-tasks.readthedocs.io/en/latest/?badge=latest)
[![PyPI](https://img.shields.io/pypi/v/django-background-tasks.svg)](https://pypi.python.org/pypi/django-background-tasks)

# Important
This is a fork of the orignal fork in order to add the missing migrations folder so we don't have to run makemigrations when ref this library. 

# Release library
In order to publish the library to pypi simply run the following commands:

## Upload package to Test Pypi
```
python setup.py register -r pypitest
```
This will attempt to register your package against PyPI's test server, just to make sure you've set up everything correctly.

Then run: 
```
python setup.py sdist upload -r pypitest
```
You should get no errors, and should also now be able to see your library in the test PyPI repository.


## Upload package to Pypi
Once you've successfully uploaded to PyPI Test, perform the same steps but point to the live PyPI server instead. To register, run:
```
python setup.py register -r pypi
```

Then, run:
```
python setup.py sdist upload -r pypi
```
and you're done!


# Original Documentation
Django Background Task is a databased-backed work queue for Django, loosely based around [Ruby's DelayedJob](https://github.com/tobi/delayed_job) library. This project was adopted and adapted from [lilspikey](https://github.com/lilspikey/) django-background-task.

To avoid conflicts on PyPI we renamed it to django-background-tasks (plural). For an easy upgrade from django-background-task to django-background-tasks, the internal module structure were left untouched.

In Django Background Task, all tasks are implemented as functions (or any other callable).

There are two parts to using background tasks:

* creating the task functions and registering them with the scheduler
* setup a cron task (or long running process) to execute the tasks


## Docs
See http://django-background-tasks.readthedocs.io/en/latest/.
