# -*- coding: utf-8 -*-


class BackgroundTaskError(Exception):

    def __init__(self, message, errors=None):
        super(BackgroundTaskError, self).__init__(message)
        self.errors = errors


class InvalidTaskError(BackgroundTaskError):
	"""
	The task will not be rescheduled if it fails with this error
	"""
	pass
