#
# Copyright 2012-2017 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#

from __future__ import absolute_import
from __future__ import division

import os
import os.path
import six
import sys
import threading
import time

import pytest

from vdsm.common import constants
from vdsm.common import commands


class TestExecCmd:
    CMD_TYPES = [tuple, list, iter]

    @pytest.mark.parametrize("cmd", CMD_TYPES)
    def test_normal(self, cmd):
        rc, out, _ = commands.execCmd(cmd(('echo', 'hello world')))
        assert rc == 0
        assert out[0].decode() == 'hello world'

    @pytest.mark.parametrize("cmd", CMD_TYPES)
    def test_io_class(self, cmd):
        rc, out, _ = commands.execCmd(cmd(('ionice',)), ioclass=2,
                                      ioclassdata=3)
        assert rc == 0
        assert out[0].decode().strip() == 'best-effort: prio 3'

    @pytest.mark.parametrize("cmd", CMD_TYPES)
    def test_nice(self, cmd):
        rc, out, _ = commands.execCmd(cmd(('cat', '/proc/self/stat')), nice=7)
        assert rc == 0
        assert int(out[0].split()[18]) == 7

    @pytest.mark.parametrize("cmd", CMD_TYPES)
    def test_set_sid(self, cmd):
        cmd_args = (sys.executable, '-c',
                    'from __future__ import print_function;import os;'
                    'print(os.getsid(os.getpid()))')
        rc, out, _ = commands.execCmd(cmd(cmd_args), setsid=True)
        assert int(out[0]) != os.getsid(os.getpid())

    @pytest.mark.parametrize("cmd", CMD_TYPES)
    @pytest.mark.skipif(os.getuid() != 0, reason="Requires root")
    def test_sudo(self, cmd):
        rc, out, _ = commands.execCmd(cmd(('grep',
                                      'Uid', '/proc/self/status')),
                                      sudo=True)
        assert rc == 0
        assert int(out[0].split()[2]) == 0


class TestExecCmdStress:

    CONCURRENCY = 50
    FUNC_DELAY = 0.01
    FUNC_CALLS = 40
    BLOCK_SIZE = 4096
    BLOCK_COUNT = 256

    def setup_method(self, test_method):
        self.data = None  # Written to process stdin
        self.workers = []
        self.resume = threading.Event()

    @pytest.mark.stress
    def test_read_stderr(self):
        self.check(self.read_stderr)

    @pytest.mark.stress
    def test_read_stdout_stderr(self):
        self.check(self.read_stdout_stderr)

    @pytest.mark.stress
    def test_write_stdin_read_stderr(self):
        self.data = 'x' * self.BLOCK_SIZE * self.BLOCK_COUNT
        self.check(self.write_stdin_read_stderr)

    def check(self, func):
        for i in range(self.CONCURRENCY):
            worker = Worker(self.resume, func, self.FUNC_CALLS,
                            self.FUNC_DELAY)
            self.workers.append(worker)
            worker.start()
        for worker in self.workers:
            worker.wait()
        self.resume.set()
        for worker in self.workers:
            worker.join()
        for worker in self.workers:
            if worker.exc_info:
                t, v, tb = worker.exc_info
                six.reraise(t, v, tb)

    def read_stderr(self):
        args = ['if=/dev/zero',
                'of=/dev/null',
                'bs=%d' % self.BLOCK_SIZE,
                'count=%d' % self.BLOCK_COUNT]
        self.run_dd(args)

    def read_stdout_stderr(self):
        args = ['if=/dev/zero',
                'bs=%d' % self.BLOCK_SIZE,
                'count=%d' % self.BLOCK_COUNT]
        out = self.run_dd(args)
        size = self.BLOCK_SIZE * self.BLOCK_COUNT
        assert len(out) == size, "Partial read: {}/{}".format(len(out), size)

    def write_stdin_read_stderr(self):
        args = ['of=/dev/null',
                'bs=%d' % self.BLOCK_SIZE,
                'count=%d' % self.BLOCK_COUNT]
        self.run_dd(args)

    def run_dd(self, args):
        cmd = [constants.EXT_DD]
        cmd.extend(args)
        rc, out, err = commands.execCmd(cmd, raw=True, data=self.data)
        assert rc == 0, "Process failed: rc={} err={}".format(rc, err)
        assert err != '', "No data from stderr"
        return out


class Worker(object):

    def __init__(self, resume, func, func_calls, func_delay):
        self.exc_info = None
        self._resume = resume
        self._func = func
        self._func_calls = func_calls
        self._func_delay = func_delay
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run)
        self._thread.daemon = True

    def start(self):
        self._thread.start()

    def wait(self):
        self._ready.wait()

    def join(self):
        self._thread.join()

    def _run(self):
        try:
            self._ready.set()
            self._resume.wait()
            for n in range(self._func_calls):
                self._func()
                time.sleep(self._func_delay)
        except Exception:
            self.exc_info = sys.exc_info()
