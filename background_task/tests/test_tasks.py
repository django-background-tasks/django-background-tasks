# -*- coding: utf-8 -*-
import time
from datetime import timedelta, datetime
from mock import patch

from django.contrib.auth.models import User
from django.test import override_settings
from django.test.testcases import TransactionTestCase
from django.conf import settings
from django.utils import timezone

from background_task.tasks import tasks, TaskSchedule, TaskProxy
from background_task.models import Task
from background_task.models_completed import CompletedTask
from background_task import background
from background_task.settings import app_settings

_recorded = []


def mocked_run_task(name, args=None, kwargs=None):
    """
    We mock tasks.run_task to give other threads some time to update the database.

    Otherwise we run into a locked database.
    """
    val = tasks.run_task(name, args, kwargs)
    if app_settings.BACKGROUND_TASK_RUN_ASYNC:
        time.sleep(1)
    return val


def mocked_run_next_task(queue=None):
    """
    We mock tasks.mocked_run_next_task to give other threads some time to update the database.

    Otherwise we run into a locked database.
    """
    val = tasks.run_next_task(queue)
    if app_settings.BACKGROUND_TASK_RUN_ASYNC:
        time.sleep(1)
    return val

run_task = mocked_run_task
run_next_task = mocked_run_next_task


def empty_task():
    pass


def record_task(*arg, **kw):
    _recorded.append((arg, kw))


class TestBackgroundDecorator(TransactionTestCase):

    def test_get_proxy(self):
        proxy = tasks.background()(empty_task)
        self.assertNotEqual(proxy, empty_task)
        self.assertTrue(isinstance(proxy, TaskProxy))

        # and alternate form
        proxy = tasks.background(empty_task)
        self.assertNotEqual(proxy, empty_task)
        self.assertTrue(isinstance(proxy, TaskProxy))

    def test_default_name(self):
        proxy = tasks.background()(empty_task)
        self.assertEqual(proxy.name, 'background_task.tests.test_tasks.empty_task')

        proxy = tasks.background()(record_task)
        self.assertEqual(proxy.name, 'background_task.tests.test_tasks.record_task')

        proxy = tasks.background(empty_task)
        # print proxy
        self.assertTrue(isinstance(proxy, TaskProxy))
        self.assertEqual(proxy.name, 'background_task.tests.test_tasks.empty_task')

    def test_specified_name(self):
        proxy = tasks.background(name='mytask')(empty_task)
        self.assertEqual(proxy.name, 'mytask')

    def test_task_function(self):
        proxy = tasks.background()(empty_task)
        self.assertEqual(proxy.task_function, empty_task)

        proxy = tasks.background()(record_task)
        self.assertEqual(proxy.task_function, record_task)

    def test_default_schedule(self):
        proxy = tasks.background()(empty_task)
        self.assertEqual(TaskSchedule(), proxy.schedule)

    def test_schedule(self):
        proxy = tasks.background(schedule=10)(empty_task)
        self.assertEqual(TaskSchedule(run_at=10), proxy.schedule)

    def test_str(self):
        proxy = tasks.background()(empty_task)
        self.assertEqual(
            u'TaskProxy(background_task.tests.test_tasks.empty_task)',
            str(proxy)
        )

    def test_shortcut(self):
        '''check shortcut to decorator works'''
        proxy = background()(empty_task)
        self.failIfEqual(proxy, empty_task)
        self.assertEqual(proxy.task_function, empty_task)

    def test_launch_sync(self):
        ''' Check launch original function in synchronous mode '''
        @background
        def add(x, y):
            return x + y

        t = Task.objects.count()
        ct = CompletedTask.objects.count()
        answer = add.now(2, 3)
        self.assertEqual(answer, 5)
        self.assertEqual(Task.objects.count(), t, 'Task was created')
        self.assertEqual(CompletedTask.objects.count(), ct, 'Completed task was created')


class TestTaskProxy(TransactionTestCase):

    def setUp(self):
        super(TestTaskProxy, self).setUp()
        self.proxy = tasks.background()(record_task)

    def test_run_task(self):
        run_task(self.proxy.name, [], {})
        self.assertEqual(((), {}), _recorded.pop())

        run_task(self.proxy.name, ['hi'], {})
        self.assertEqual((('hi',), {}), _recorded.pop())

        run_task(self.proxy.name, [], {'kw': 1})
        self.assertEqual(((), {'kw': 1}), _recorded.pop())


class TestTaskSchedule(TransactionTestCase):

    def test_priority(self):
        self.assertEqual(0, TaskSchedule().priority)
        self.assertEqual(0, TaskSchedule(priority=0).priority)
        self.assertEqual(1, TaskSchedule(priority=1).priority)
        self.assertEqual(2, TaskSchedule(priority=2).priority)

    def _within_one_second(self, d1, d2):
        self.failUnless(isinstance(d1, datetime))
        self.failUnless(isinstance(d2, datetime))
        self.failUnless(abs(d1 - d2) <= timedelta(seconds=1))

    def test_run_at(self):
        for schedule in [None, 0, timedelta(seconds=0)]:
            now = timezone.now()
            run_at = TaskSchedule(run_at=schedule).run_at
            self._within_one_second(run_at, now)

        now = timezone.now()
        run_at = TaskSchedule(run_at=now).run_at
        self._within_one_second(run_at, now)

        fixed_dt = timezone.now() + timedelta(seconds=60)
        run_at = TaskSchedule(run_at=fixed_dt).run_at
        self._within_one_second(run_at, fixed_dt)

        run_at = TaskSchedule(run_at=90).run_at
        self._within_one_second(run_at, timezone.now() + timedelta(seconds=90))

        run_at = TaskSchedule(run_at=timedelta(seconds=35)).run_at
        self._within_one_second(run_at, timezone.now() + timedelta(seconds=35))

    def test_create(self):
        fixed_dt = timezone.now() + timedelta(seconds=10)
        schedule = TaskSchedule.create({'run_at': fixed_dt})
        self.assertEqual(schedule.run_at, fixed_dt)
        self.assertEqual(0, schedule.priority)
        self.assertEqual(TaskSchedule.SCHEDULE, schedule.action)

        schedule = {'run_at': fixed_dt, 'priority': 2,
                    'action': TaskSchedule.RESCHEDULE_EXISTING}
        schedule = TaskSchedule.create(schedule)
        self.assertEqual(schedule.run_at, fixed_dt)
        self.assertEqual(2, schedule.priority)
        self.assertEqual(TaskSchedule.RESCHEDULE_EXISTING, schedule.action)

        schedule = TaskSchedule.create(0)
        self._within_one_second(schedule.run_at, timezone.now())

        schedule = TaskSchedule.create(10)
        self._within_one_second(schedule.run_at,
                                timezone.now() + timedelta(seconds=10))

        schedule = TaskSchedule.create(TaskSchedule(run_at=fixed_dt))
        self.assertEqual(schedule.run_at, fixed_dt)
        self.assertEqual(0, schedule.priority)
        self.assertEqual(TaskSchedule.SCHEDULE, schedule.action)

    def test_merge(self):
        default = TaskSchedule(run_at=10, priority=2,
                               action=TaskSchedule.RESCHEDULE_EXISTING)
        schedule = TaskSchedule.create(20).merge(default)

        self._within_one_second(timezone.now() + timedelta(seconds=20),
                                schedule.run_at)
        self.assertEqual(2, schedule.priority)
        self.assertEqual(TaskSchedule.RESCHEDULE_EXISTING, schedule.action)

        schedule = TaskSchedule.create({'priority': 0}).merge(default)
        self._within_one_second(timezone.now() + timedelta(seconds=10),
                                schedule.run_at)
        self.assertEqual(0, schedule.priority)
        self.assertEqual(TaskSchedule.RESCHEDULE_EXISTING, schedule.action)

        action = TaskSchedule.CHECK_EXISTING
        schedule = TaskSchedule.create({'action': action}).merge(default)
        self._within_one_second(timezone.now() + timedelta(seconds=10),
                                schedule.run_at)
        self.assertEqual(2, schedule.priority)
        self.assertEqual(action, schedule.action)

    def test_repr(self):
        self.assertEqual('TaskSchedule(run_at=10, priority=0)',
                            repr(TaskSchedule(run_at=10, priority=0)))


class TestSchedulingTasks(TransactionTestCase):

    def test_background_gets_scheduled(self):
        self.result = None

        @tasks.background(name='test_background_gets_scheduled')
        def set_result(result):
            self.result = result

        # calling set_result should now actually create a record in the db
        set_result(1)

        all_tasks = Task.objects.all()
        self.assertEqual(1, all_tasks.count())
        task = all_tasks[0]
        self.assertEqual('test_background_gets_scheduled', task.task_name)
        self.assertEqual('[[1], {}]', task.task_params)

    def test_reschedule_existing(self):

        reschedule_existing = TaskSchedule.RESCHEDULE_EXISTING

        @tasks.background(name='test_reschedule_existing',
                         schedule=TaskSchedule(action=reschedule_existing))
        def reschedule_fn():
            pass

        # this should only end up with one task
        # and it should be scheduled for the later time
        reschedule_fn()
        reschedule_fn(schedule=90)

        all_tasks = Task.objects.all()
        self.assertEqual(1, all_tasks.count())
        task = all_tasks[0]
        self.assertEqual('test_reschedule_existing', task.task_name)

        # check task is scheduled for later on
        now = timezone.now()
        self.failUnless(now + timedelta(seconds=89) < task.run_at)
        self.failUnless(now + timedelta(seconds=91) > task.run_at)

    def test_check_existing(self):

        check_existing = TaskSchedule.CHECK_EXISTING

        @tasks.background(name='test_check_existing',
                         schedule=TaskSchedule(action=check_existing))
        def check_fn():
            pass

        # this should only end up with the first call
        # scheduled
        check_fn()
        check_fn(schedule=90)

        all_tasks = Task.objects.all()
        self.assertEqual(1, all_tasks.count())
        task = all_tasks[0]
        self.assertEqual('test_check_existing', task.task_name)

        # check new task is scheduled for the earlier time
        now = timezone.now()
        self.failUnless(now - timedelta(seconds=1) < task.run_at)
        self.failUnless(now + timedelta(seconds=1) > task.run_at)


class TestTaskRunner(TransactionTestCase):

    def setUp(self):
        super(TestTaskRunner, self).setUp()
        self.runner = tasks._runner

    def test_get_task_to_run_no_tasks(self):
        self.failIf(self.runner.get_task_to_run(tasks))

    def test_get_task_to_run(self):
        task = Task.objects.new_task('mytask', (1), {})
        task.save()
        self.failUnless(task.locked_by is None)
        self.failUnless(task.locked_at is None)

        locked_task = self.runner.get_task_to_run(tasks)
        self.failIf(locked_task is None)
        self.failIf(locked_task.locked_by is None)
        self.assertEqual(self.runner.worker_name, locked_task.locked_by)
        self.failIf(locked_task.locked_at is None)
        self.assertEqual('mytask', locked_task.task_name)


class TestTaskModel(TransactionTestCase):

    def test_lock_uncontested(self):
        task = Task.objects.new_task('mytask')
        task.save()
        self.failUnless(task.locked_by is None)
        self.failUnless(task.locked_at is None)

        locked_task = task.lock('mylock')
        self.assertEqual('mylock', locked_task.locked_by)
        self.failIf(locked_task.locked_at is None)
        self.assertEqual(task.pk, locked_task.pk)

    def test_lock_contested(self):
        # locking should actually look at db, not object
        # in memory
        task = Task.objects.new_task('mytask')
        task.save()
        self.failIf(task.lock('mylock') is None)

        self.failUnless(task.lock('otherlock') is None)

    def test_lock_expired(self):
        task = Task.objects.new_task('mytask')
        task.save()
        locked_task = task.lock('mylock')

        # force expire the lock
        expire_by = timedelta(seconds=(app_settings.BACKGROUND_TASK_MAX_RUN_TIME + 2))
        locked_task.locked_at = locked_task.locked_at - expire_by
        locked_task.save()

        # now try to get the lock again
        self.failIf(task.lock('otherlock') is None)

    def test_str(self):
        task = Task.objects.new_task('mytask')
        self.assertEqual(u'mytask', str(task))
        task = Task.objects.new_task('mytask', verbose_name="My Task")
        self.assertEqual(u'My Task', str(task))

    def test_creator(self):
        user = User.objects.create_user(username='bob', email='bob@example.com', password='12345')
        task = Task.objects.new_task('mytask', creator=user)
        task.save()
        self.assertEqual(task.creator, user)

    def test_repeat(self):
        repeat_until = timezone.now() + timedelta(days=1)
        task = Task.objects.new_task('mytask', repeat=Task.HOURLY, repeat_until=repeat_until)
        task.save()
        self.assertEqual(task.repeat, Task.HOURLY)
        self.assertEqual(task.repeat_until, repeat_until)

    def test_create_completed_task(self):
        task = Task.objects.new_task(
            task_name='mytask',
            args=[1],
            kwargs={'q': 's'},
            priority=1,
            queue='myqueue',
            verbose_name='My Task',
            creator=User.objects.create_user(username='bob', email='bob@example.com', password='12345'),
        )
        task.save()
        completed_task = task.create_completed_task()
        self.assertEqual(completed_task.task_name, task.task_name)
        self.assertEqual(completed_task.task_params, task.task_params)
        self.assertEqual(completed_task.priority, task.priority)
        self.assertEqual(completed_task.queue, task.queue)
        self.assertEqual(completed_task.verbose_name, task.verbose_name)
        self.assertEqual(completed_task.creator, task.creator)
        self.assertEqual(completed_task.repeat, task.repeat)
        self.assertEqual(completed_task.repeat_until, task.repeat_until)


class TestTasks(TransactionTestCase):

    def setUp(self):
        super(TestTasks, self).setUp()

        @tasks.background(name='set_fields')
        def set_fields(**fields):
            for key, value in fields.items():
                setattr(self, key, value)

        @tasks.background(name='throws_error')
        def throws_error():
            raise RuntimeError("an error")

        self.set_fields = set_fields
        self.throws_error = throws_error

    def test_run_next_task_nothing_scheduled(self):
        self.failIf(run_next_task())

    def test_run_next_task_one_task_scheduled(self):
        self.set_fields(worked=True)
        self.failIf(hasattr(self, 'worked'))

        self.failUnless(run_next_task())

        self.failUnless(hasattr(self, 'worked'))
        self.failUnless(self.worked)

    def test_run_next_task_several_tasks_scheduled(self):
        self.set_fields(one='1')
        self.set_fields(two='2')
        self.set_fields(three='3')

        for i in range(3):
            self.failUnless(run_next_task())

        self.failIf(run_next_task())  # everything should have been run

        for field, value in [('one', '1'), ('two', '2'), ('three', '3')]:
            self.failUnless(hasattr(self, field))
            self.assertEqual(value, getattr(self, field))

    def test_run_next_task_error_handling(self):
        self.throws_error()

        all_tasks = Task.objects.all()
        self.assertEqual(1, all_tasks.count())
        original_task = all_tasks[0]

        # should run, but trigger error
        self.failUnless(run_next_task())

        all_tasks = Task.objects.all()
        self.assertEqual(1, all_tasks.count())

        failed_task = all_tasks[0]
        # should have an error recorded
        self.failIfEqual('', failed_task.last_error)
        self.failUnless(failed_task.failed_at is None)
        self.assertEqual(1, failed_task.attempts)

        # should have been rescheduled for the future
        # and no longer locked
        self.failUnless(failed_task.run_at > original_task.run_at)
        self.failUnless(failed_task.locked_by is None)
        self.failUnless(failed_task.locked_at is None)

    def test_run_next_task_does_not_run_locked(self):
        self.set_fields(locked=True)
        self.failIf(hasattr(self, 'locked'))

        all_tasks = Task.objects.all()
        self.assertEqual(1, all_tasks.count())
        original_task = all_tasks[0]
        original_task.lock('lockname')

        self.failIf(run_next_task())

        self.failIf(hasattr(self, 'locked'))
        all_tasks = Task.objects.all()
        self.assertEqual(1, all_tasks.count())

    def test_run_next_task_unlocks_after_MAX_RUN_TIME(self):
        self.set_fields(lock_overridden=True)

        all_tasks = Task.objects.all()
        self.assertEqual(1, all_tasks.count())
        original_task = all_tasks[0]
        locked_task = original_task.lock('lockname')

        self.failIf(run_next_task())

        self.failIf(hasattr(self, 'lock_overridden'))

        # put lot time into past
        expire_by = timedelta(seconds=(app_settings.BACKGROUND_TASK_MAX_RUN_TIME + 2))
        locked_task.locked_at = locked_task.locked_at - expire_by
        locked_task.save()

        # so now we should be able to override the lock
        # and run the task
        self.failUnless(run_next_task())
        self.assertEqual(0, Task.objects.count())

        self.failUnless(hasattr(self, 'lock_overridden'))
        self.failUnless(self.lock_overridden)

    def test_default_schedule_used_for_run_at(self):

        @tasks.background(name='default_schedule_used_for_run_at', schedule=60)
        def default_schedule_used_for_time():
            pass

        now = timezone.now()
        default_schedule_used_for_time()

        all_tasks = Task.objects.all()
        self.assertEqual(1, all_tasks.count())
        task = all_tasks[0]

        self.failUnless(now < task.run_at)
        self.failUnless((task.run_at - now) <= timedelta(seconds=61))
        self.failUnless((task.run_at - now) >= timedelta(seconds=59))

    def test_default_schedule_used_for_priority(self):

        @tasks.background(name='default_schedule_used_for_priority',
                          schedule={'priority': 2})
        def default_schedule_used_for_priority():
            pass

        default_schedule_used_for_priority()

        all_tasks = Task.objects.all()
        self.assertEqual(1, all_tasks.count())
        task = all_tasks[0]
        self.assertEqual(2, task.priority)

    def test_non_default_schedule_used(self):
        default_run_at = timezone.now() + timedelta(seconds=90)

        @tasks.background(name='non_default_schedule_used',
                          schedule={'run_at': default_run_at, 'priority': 2})
        def default_schedule_used_for_priority():
            pass

        run_at = timezone.now().replace(microsecond=0) + timedelta(seconds=60)
        default_schedule_used_for_priority(schedule=run_at)

        all_tasks = Task.objects.all()
        self.assertEqual(1, all_tasks.count())
        task = all_tasks[0]
        self.assertEqual(run_at, task.run_at)

    def test_failed_at_set_after_MAX_ATTEMPTS(self):
        @tasks.background(name='test_failed_at_set_after_MAX_ATTEMPTS')
        def failed_at_set_after_MAX_ATTEMPTS():
            raise RuntimeError('failed')

        failed_at_set_after_MAX_ATTEMPTS()

        available = Task.objects.find_available()
        self.assertEqual(1, available.count())
        task = available[0]

        self.failUnless(task.failed_at is None)

        task.attempts = app_settings.BACKGROUND_TASK_MAX_ATTEMPTS
        task.save()

        # task should be scheduled to run now
        # but will be marked as failed straight away
        self.failUnless(run_next_task())

        available = Task.objects.find_available()
        self.assertEqual(0, available.count())

        all_tasks = Task.objects.all()
        self.assertEqual(0, all_tasks.count())
        self.assertEqual(1, CompletedTask.objects.count())
        completed_task = CompletedTask.objects.all()[0]
        self.failIf(completed_task.failed_at is None)

    def test_run_task_return_value(self):
        return_value = self.set_fields(test='test')
        self.assertEqual(Task.objects.count(), 1)
        task = Task.objects.first()
        self.assertEqual(return_value, task)
        self.assertEqual(return_value.pk, task.pk)

    def test_verbose_name_param(self):
        verbose_name = 'My Task'
        task = self.set_fields(test='test1', verbose_name=verbose_name)
        self.assertEqual(task.verbose_name, verbose_name)

    def test_creator_param(self):
        user = User.objects.create_user(username='bob', email='bob@example.com', password='12345')
        task = self.set_fields(test='test2', creator=user)
        self.assertEqual(task.creator, user)


class MaxAttemptsTestCase(TransactionTestCase):

    def setUp(self):
        @tasks.background(name='failing task')
        def failing_task():
            raise Exception("error")
            # return 0 / 0
        self.failing_task = failing_task
        self.task1 = self.failing_task()
        self.task2 = self.failing_task()
        self.task1_id = self.task1.id
        self.task2_id = self.task2.id

    @override_settings(MAX_ATTEMPTS=1)
    def test_max_attempts_one(self):
        self.assertEqual(settings.MAX_ATTEMPTS, 1)
        self.assertEqual(Task.objects.count(), 2)

        run_next_task()
        self.assertEqual(Task.objects.count(), 1)
        self.assertEqual(Task.objects.all()[0].id, self.task2_id)
        self.assertEqual(CompletedTask.objects.count(), 1)
        completed_task = CompletedTask.objects.all()[0]
        self.assertEqual(completed_task.attempts, 1)
        self.assertEqual(completed_task.task_name, self.task1.task_name)
        self.assertEqual(completed_task.task_params, self.task1.task_params)
        self.assertIsNotNone(completed_task.last_error)
        self.assertIsNotNone(completed_task.failed_at)

        run_next_task()
        self.assertEqual(Task.objects.count(), 0)
        self.assertEqual(CompletedTask.objects.count(), 2)

    @override_settings(MAX_ATTEMPTS=2)
    def test_max_attempts_two(self):
        self.assertEqual(settings.MAX_ATTEMPTS, 2)
        run_next_task()
        self.assertEqual(Task.objects.count(), 2)
        self.assertEqual(CompletedTask.objects.count(), 0)


class ArgumentsWithDictTestCase(TransactionTestCase):
    def setUp(self):
        @tasks.background(name='failing task')
        def task(d):
            pass
        self.task = task

    def test_task_with_dictionary_in_args(self):
        self.assertEqual(Task.objects.count(), 0)
        d = {22222: 2, 11111: 1}
        self.task(d)
        self.assertEqual(Task.objects.count(), 1)
        run_next_task()
        self.assertEqual(Task.objects.count(), 0)


completed_named_queue_tasks = []


@background(queue='named_queue')
def named_queue_task(message):
    completed_named_queue_tasks.append(message)


class NamedQueueTestCase(TransactionTestCase):

    def test_process_queue(self):
        named_queue_task('test1')
        run_next_task(queue='named_queue')
        self.assertIn('test1', completed_named_queue_tasks, msg='Task should be processed')

    def test_process_all_tasks(self):
        named_queue_task('test2')
        run_next_task()
        self.assertIn('test2', completed_named_queue_tasks, msg='Task should be processed')

    def test_process_other_queue(self):
        named_queue_task('test3')
        run_next_task(queue='other_named_queue')
        self.assertNotIn('test3', completed_named_queue_tasks, msg='Task should be ignored')
        run_next_task()


class RepetitionTestCase(TransactionTestCase):

    def setUp(self):
        @tasks.background()
        def my_task(*args, **kwargs):
            pass
        self.my_task = my_task

    def test_repeat(self):
        repeat_until = timezone.now() + timedelta(weeks=1)
        old_task = self.my_task(
            'test-repeat',
            foo='bar',
            repeat=Task.HOURLY,
            repeat_until=repeat_until,
            verbose_name="Test repeat",
        )
        self.assertEqual(old_task.repeat, Task.HOURLY)
        self.assertEqual(old_task.repeat_until, repeat_until)
        tasks.run_next_task()
        time.sleep(0.5)

        self.assertEqual(Task.objects.filter(repeat=Task.HOURLY).count(), 1)
        new_task = Task.objects.get(repeat=Task.HOURLY)
        self.assertNotEqual(new_task.id, old_task.id)
        self.assertEqual(new_task.task_name, old_task.task_name)
        self.assertEqual(new_task.params(), old_task.params())
        self.assertEqual(new_task.task_hash, old_task.task_hash)
        self.assertEqual(new_task.verbose_name, old_task.verbose_name)
        self.assertEqual((new_task.run_at - old_task.run_at), timedelta(hours=1))
        self.assertEqual(new_task.repeat_until, old_task.repeat_until)

    def test_repetition_in_future(self):
        repeat_until = timezone.now() + timedelta(weeks=1)
        old_task = self.my_task(
            'test-repetition',
            repeat=Task.HOURLY,
            repeat_until=repeat_until,
            verbose_name="Test repetition in future",
        )
        old_task.run_at = timezone.now() - timedelta(weeks=1)  # task is one week old
        old_task.save()
        tasks.run_next_task()
        time.sleep(0.5)

        self.assertEqual(Task.objects.filter(repeat=Task.HOURLY).count(), 1)
        new_task = Task.objects.get(repeat=Task.HOURLY)
        self.assertNotEqual(new_task.id, old_task.id)
        # new task skipped exactly one week of downtime in the past, keeps period
        self.assertEqual((new_task.run_at - old_task.run_at), timedelta(weeks=1, hours=1))
        # new task will be executed in the future
        self.assertTrue(new_task.run_at > timezone.now())
        # new task will be executed in less than one hour
        self.assertTrue((new_task.run_at - timezone.now()) <= timedelta(hours=1))


class QuerySetManagerTestCase(TransactionTestCase):

    def setUp(self):
        @tasks.background()
        def succeeding_task():
            return 0/1

        @tasks.background()
        def failing_task():
            return 0/0

        self.user1 = User.objects.create_user(username='bob', email='bob@example.com', password='12345')
        self.user2 = User.objects.create_user(username='bob2', email='bob@example.com', password='12345')
        self.task_all = succeeding_task()
        self.task_user = succeeding_task(creator=self.user1)
        self.failing_task_all = failing_task()
        self.failing_task_user = failing_task(creator=self.user1)

    @override_settings(MAX_ATTEMPTS=1)
    def test_task_manager(self):
        self.assertEqual(len(Task.objects.all()), 4)
        self.assertEqual(len(Task.objects.created_by(self.user1)), 2)
        self.assertEqual(len(Task.objects.created_by(self.user2)), 0)
        for i in range(4):
            run_next_task()
        self.assertEqual(len(Task.objects.all()), 0)
        self.assertEqual(len(Task.objects.created_by(self.user1)), 0)
        self.assertEqual(len(Task.objects.created_by(self.user2)), 0)

    @override_settings(MAX_ATTEMPTS=1)
    def test_completed_task_manager(self):
        self.assertEqual(len(CompletedTask.objects.created_by(self.user1)), 0)
        self.assertEqual(len(CompletedTask.objects.created_by(self.user2)), 0)
        self.assertEqual(len(CompletedTask.objects.failed()), 0)
        self.assertEqual(len(CompletedTask.objects.created_by(self.user1).failed()), 0)
        self.assertEqual(len(CompletedTask.objects.failed(within=timedelta(hours=1))), 0)
        self.assertEqual(len(CompletedTask.objects.succeeded()), 0)
        self.assertEqual(len(CompletedTask.objects.created_by(self.user1).succeeded()), 0)
        self.assertEqual(len(CompletedTask.objects.succeeded(within=timedelta(hours=1))), 0)
        for i in range(4):
            run_next_task()
        self.assertEqual(len(CompletedTask.objects.created_by(self.user1)), 2)
        self.assertEqual(len(CompletedTask.objects.created_by(self.user2)), 0)
        self.assertEqual(len(CompletedTask.objects.failed()), 2)
        self.assertEqual(len(CompletedTask.objects.created_by(self.user1).failed()), 1)
        self.assertEqual(len(CompletedTask.objects.failed(within=timedelta(hours=1))), 2)
        self.assertEqual(len(CompletedTask.objects.succeeded()), 2)
        self.assertEqual(len(CompletedTask.objects.created_by(self.user1).succeeded()), 1)
        self.assertEqual(len(CompletedTask.objects.succeeded(within=timedelta(hours=1))), 2)


class PriorityTestCase(TransactionTestCase):

    def setUp(self):
        @tasks.background()
        def mytask():
            pass

        run_at = timezone.now() - timedelta(minutes=1)

        self.high_priority_task = mytask(priority=99, schedule=run_at)
        self.low_priority_task = mytask(priority=-1, schedule=run_at)

    def test_priority(self):
        self.assertEqual(self.high_priority_task.priority, 99)
        self.assertEqual(self.low_priority_task.priority, -1)

        available = Task.objects.find_available()
        self.assertEqual(available.count(), 2)
        self.assertEqual(available.first(), self.high_priority_task)
        # Using a list here. QuerySet.last() is prohibited after slicing (new in Django 2.0)
        self.assertEqual(list(available)[-1], self.low_priority_task)

        self.assertFalse(CompletedTask.objects.filter(priority=self.high_priority_task.priority).exists())
        self.assertFalse(CompletedTask.objects.filter(priority=self.low_priority_task.priority).exists())
        run_next_task()
        self.assertTrue(CompletedTask.objects.filter(priority=self.high_priority_task.priority).exists())
        self.assertFalse(CompletedTask.objects.filter(priority=self.low_priority_task.priority).exists())
        run_next_task()
        self.assertTrue(CompletedTask.objects.filter(priority=self.high_priority_task.priority).exists())
        self.assertTrue(CompletedTask.objects.filter(priority=self.low_priority_task.priority).exists())


class LoggingTestCase(TransactionTestCase):

    def setUp(self):
        @tasks.background()
        def succeeding_task():
            return 0/1

        @tasks.background()
        def failing_task():
            return 0/0

        self.succeeding_task = succeeding_task
        self.failing_task = failing_task

    @patch('background_task.tasks.logger')
    def test_success_logging(self, mock_logger):
        self.succeeding_task()
        run_next_task()
        self.assertFalse(mock_logger.warning.called)
        self.assertFalse(mock_logger.error.called)
        self.assertFalse(mock_logger.critical.called)

    @patch('background_task.tasks.logger')
    def test_error_logging(self, mock_logger):
        self.failing_task()
        run_next_task()
        self.assertFalse(mock_logger.warning.called)
        self.assertTrue(mock_logger.error.called)
        self.assertFalse(mock_logger.critical.called)
