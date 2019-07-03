# -*- coding: utf-8 -*-
import math
import calendar
import signal
import platform

TTW_SLOW = [0.5, 1.5]
TTW_FAST = [0.0, 0.1]


def add_months_to_datetime(dt, months):
    """Adds n number of months to a datetime, adjusting the year as necessary"""

    # Note: shifting these month values by '1' b/c Python indexes their months starting
    # at 1, which does not work with modulo (eg. 12 % 12 == 0, which is not valid)
    new_month = ((dt.month - 1 + months) % 12) + 1
    years_passed = int(math.floor((dt.month - 1 + months) / 12))
    new_year = dt.year + years_passed

    # Adjust days in case we're on the 31st which won't exist in the following month
    days_in_month = calendar.monthrange(new_year, new_month)[1]
    new_day = min(dt.day, days_in_month)

    return dt.replace(day=new_day, month=new_month, year=new_year)


class SignalManager(object):
    """Manages POSIX signals."""

    kill_now = False
    time_to_wait = TTW_FAST

    def __init__(self):
        # Temporary workaround for signals not available on Windows
        if platform.system() == 'Windows':
            signal.signal(signal.SIGTERM, self.exit_gracefully)
        else:
            signal.signal(signal.SIGTSTP, self.exit_gracefully)
            signal.signal(signal.SIGUSR1, self.speed_up)
            signal.signal(signal.SIGUSR2, self.slow_down)

    def exit_gracefully(self, signum, frame):
        self.kill_now = True

    def speed_up(self, signum, frame):
        self.time_to_wait = TTW_FAST

    def slow_down(self, signum, frame):
        self.time_to_wait = TTW_SLOW
