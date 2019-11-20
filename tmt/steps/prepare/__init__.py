# coding: utf-8

""" Prepare Step Class """

import tmt
import os
import shutil
import subprocess

from click import echo

class Prepare(tmt.steps.Step):
    name = 'prepare'

    def __init__(self, data, plan):
        """ Initialize the Prepare step """
        self.super = super(Prepare, self)
        self.super.__init__(data, plan)

    def wake(self):
        """ Wake up the step (process workdir and command line) """
        self.super.wake()

        for i in range(len(self.data)):
            self.set_default(i, 'how', 'shell')
            self.set_default(i, 'playbooks', [])
            self.set_default(i, 'path', self.data[i]['playbooks'])
            self.set_default(i, 'script', self.data[i]['path'])

    def show(self):
        """ Show discover details """
        self.super.show(keys = ['how', 'script'])

    def go(self):
        """ Prepare the test step """
        self.super.go()

        for data in self.data:
            how = data['how']
            script = data['script']

            if script:
                self.verbose('    Prepare', "{how} = '{script}".format(**locals()), 'yellow')

                try:
                    self.plan.provision.prepare(how, script)
                except AttributeError as error:
                    raise SpecificationError('NYI: cannot currently run this preparator.')

            else:
                self.debug('Note', "No path/script defined for prepare({how})".format(**locals()), 'yellow')

        # TODO: find a better way
        packages = self.plan.execute.requires()
        if packages:
            self.plan.provision.prepare('shell', "sleep 1; set -x; nohup bash -c 'dnf install -y {' '.join(packages)}' 1>/root/prepare.log 2>&1 && exit 0; cat prepare.log; exit 1".format(**locals()))
            self.plan.provision.copy_from_guest('/root/prepare.log')

    def set_default(self, i, where, default):
        if not (where in self.data[i] and self.data[i][where]):
            self.data[i][where] = default
