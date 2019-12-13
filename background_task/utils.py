# -*- coding: utf-8 -*-
import signal
import platform

TTW_SLOW = [0.5, 1.5]
TTW_FAST = [0.0, 0.1]


class SignalManager(object):
    """Manages POSIX signals."""

    kill_now = False
    time_to_wait = TTW_FAST

    def __init__(self):
        # Temporary workaround for signals not available on Windows
        if platform.system() == 'Windows':
            signal.signal(signal.SIGTERM, self.exit_gracefully)
        else:
            signal.signal(signal.SIGTERM, self.exit_gracefully)
            signal.signal(signal.SIGINT, self.exit_gracefully)
            signal.signal(signal.SIGTSTP, self.exit_gracefully)
            signal.signal(signal.SIGUSR1, self.speed_up)
            signal.signal(signal.SIGUSR2, self.slow_down)

    def exit_gracefully(self, signum, frame):
        print("[+] Process tasks has got signal ",
              signal.Signals(signum).name,
              ", exiting...")
        self.kill_now = True

    def speed_up(self, signum, frame):
        self.time_to_wait = TTW_FAST

    def slow_down(self, signum, frame):
        self.time_to_wait = TTW_SLOW
