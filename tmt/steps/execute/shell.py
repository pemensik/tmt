# coding: utf-8

""" Shell Executor Provider Class """

from tmt.steps.execute.base import ExecutorBase
from tmt.utils import RUNNER


class ExecutorShell(ExecutorBase):
    """ Run tests using how: shell """
    type = 'shell'

    def __init__(self,  data, step=None, name=None):
        super(ExecutorShell, self).__init__(data, step, name)

    def go(self, plan_workdir):
        """ Run tests """
        super(ExecutorShell, self).go(plan_workdir)
        # we need run.sh synced to workdir
        self.step.sync_runner()

        self.step.execute('nohup',
            '{self.step.workdir}/{RUNNER}'.format(**locals()),
            '-v',
            plan_workdir,
            self.type,
            '{self.step.workdir}/stdout.log'.format(**locals()),
            '{self.step.workdir}/stderr.log'.format(**locals()))

    # API
    def requires(self):
        """ Returns packages required to run tests"""
        super(ExecutorShell, self).requires()
        return ()

    def results(self):
        """ Returns results from executed tests """
        super(ExecutorShell, self).results()
