# coding: utf-8

"""
FMF Tests Discovery

Minimal config example (all available tests from the current
repository used by default)::

    discover:
        how: fmf

Full config example::

    discover:
        how: fmf
        repository: https://github.com/psss/tmt
        revision: master
        destination: tmt
        filter: 'tier: 1'
"""

import os
import re
import fmf
import tmt
import shutil
import tmt.steps.discover

from click import echo
from fmf.utils import listed

class DiscoverFmf(tmt.steps.discover.DiscoverPlugin):
    """ Discover available tests from FMF metadata """

    def __init__(self, data, step):
        """ Check supported attributes """
        super(DiscoverFmf, self).__init__(
            data=data, step=step, name=data['name'])
        self.tree = None
        # Convert data into attributes for easy handling
        self.repository = data.get('repository')
        self.revision = data.get('revision')
        filtr = data.get('filter', [])
        self.filters = filtr if isinstance(filtr, list) else [filtr]
        self._tests = []

    def go(self):
        """ Discover available tests """
        super(DiscoverFmf, self).go()
        testdir = os.path.join(self.workdir, 'tests')
        # Clone provided git repository
        if self.repository:
            self.info('repository', self.repository, 'green')
            self.debug("Clone '{self.repository}' to '{testdir}'.".format(**locals()))
            self.run('git clone {self.repository} {testdir}'.format(**locals()))
        # Copy current directory to workdir
        else:
            directory = self.step.plan.run.tree.root
            self.info('directory', directory, 'green')
            self.debug("Copy '{}' to '{}'.".format(directory, testdir))
            shutil.copytree(directory, testdir)
        # Checkout revision if requested
        if self.revision:
            self.info('revision', self.revision, 'green')
            self.debug("Checkout revision '{self.revision}'.".format(**locals()))
            self.run("git checkout -f {self.revision}".format(**locals()), cwd=testdir)
        # Show filters if provided
        if self.filters:
            for filter_ in self.filters:
                self.info('filter', filter_, 'green')
        # Initialize the metadata tree
        self.debug("Check metadata tree in '{testdir}'.".format(**locals()))
        # Nothing more to do here when in dry mode
        if self.opt('dry'):
            return []
        tests = tmt.Tree(testdir).tests(filters=self.filters)
        # Modify test names and paths to make them unique
        for test in tests:
            test.name = "/{self.name}{test.name}".format(**locals())
            test.path = "/{self.name}/tests{test.path}".format(**locals())
        # Summary of selected tests, test list in verbose mode
        self.info('tests', listed(len(tests), 'test') + ' selected', 'green')
        for test in tests:
            self.verbose(test.name, color='red', shift=1)
        self._tests = tests

    def tests(self):
        """ Return all discovered tests """
        return self._tests

    def dump(self):
        """ Dump current step data """
        self.data['filter'] = self.filters
        return self.data
