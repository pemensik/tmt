# coding: utf-8

""" Provision Step Vagrnat Class """

import tmt
import subprocess
import os
import re

from tmt.steps.provision.base import ProvisionBase
from tmt.utils import ConvertError, SpecificationError, GeneralError

from click import echo
try:
    from urllib.parse import urlparse
except ImportError:
    import urlparse


# DATA[*]:
#   HOW = libvirt|virtual|docker|container|vagrant|...
#         provider, in Vagrant's terminilogy
#
#   IMAGE = URI|NAME
#         NAME is for Vagrant or other HOW, passed directly
#         URI can be path to BOX, QCOW2 or Vagrantfile f.e.
#
#   BOX = Set a BOX name directly (in case of URI for IMAGE)
#
class ProvisionVagrant(ProvisionBase):
    """ Use Vagrant to Provision an environment for testing """
    executable = 'vagrant'
    config_prefix = '  config.'
    sync_type = 'rsync'
    default_image = 'fedora/31-cloud-base'
    default_container = 'fedora:latest'
    default_indent = 16
    vf_name = 'Vagrantfile'
    timeout = 333
    eol = '\n'

    ## Default API ##
    def __init__(self, data, step):
        """ Initialize the Vagrant provision step """
        self.super = super(ProvisionVagrant, self)
        self.super.__init__(data, step)
        self.vagrantfile = os.path.join(self.provision_dir, self.vf_name)
        self.vf_data = ''
        self.path = os.path.join(self.provision_dir, 'data.yaml')

        # Check for working Vagrant
        self.run_vagrant('version')

        # Let's check what's needed
        self.check_how()

    def load(self):
        """ Load ProvisionVagrant step """
        raise SpecificationError("NYI: cannot load")
        self.super.load()

    def save(self):
        """ Save ProvisionVagrant step """
        raise SpecificationError("NYI: cannot save")
        self.super.save()

    def go(self):
        """ Execute actual provisioning """
        self.init()
        self.info('Provisioning {self.executable}, {self.vf_name}'.format(**locals()), self.vf_read())
        return self.run_vagrant('up')

    def execute(self, *args, **kwargs):
        """ Execute remote command """
        return self.run_vagrant('ssh', '-c', self.join(args))

    def show(self):
        """ Create and show the Vagrantfile """
        self.init()
        self.super.show(keys=['how', 'box', 'image'])
        self.info(self.vf_name, self.vf_read())

    def sync_workdir_to_guest(self):
        """ sync on demand """
        return self.run_vagrant('rsync')

    def sync_workdir_from_guest(self):
        """ sync from guest to host """
        command = 'rsync-back'
        self.plugin_install(command)
        return self.run_vagrant(command)

    def copy_from_guest(self, target):
        """ copy file/folder from guest to host's copy dir """
        beg = "[[ -d '{target}' ]]".format(**locals())
        end = 'exit 0; set -xe; '

        isdir = "{beg} || {end}".format(**locals())
        isntdir = "{beg} && {end}".format(**locals())

        target_dir = '{self.provision_dir}/copy/{target}'.format(**locals())
        self.execute(isdir + self.cmd_mkcp(target_dir, '{target}/.'.format(**locals())))

        target_dir = '$(dirname "{self.provision_dir}/copy/{target}")'.format(**locals())
        self.execute(isntdir + self.cmd_mkcp(target_dir, target))

        self.sync_workdir_from_guest()

    def destroy(self):
        """ remove instance """
        return self.run_vagrant('destroy', '-f')

    def prepare(self, how, what):
        """ add single 'preparator' and run it """

        name = 'prepare'
        cmd = 'provision'

        # TODO: FIX
        whatpath = os.path.join(self.step.plan.workdir,
            'discover',
            'one',
            'tests',
            what)

        self.debug('Trying path', whatpath)

        if os.path.exists(whatpath) and os.path.isfile(whatpath):
            what = whatpath

        if how == 'ansible':
            name = how

            self.add_config_block(cmd,
                name,
                'become = true'.format(**locals()),
                'become_user = "root"'.format(**locals()),
                'playbook = "{what}"'.format(**locals()))
           #TODO: run: 'never'

        else:
            if self.is_uri(what):
                method = 'path'
            else:
                method = 'inline'

            self.add_config('vm',
                cmd,
                self.quote(name),
                self.kv('type', how),
                self.kv('privileged', 'true'),
                self.kv('run', 'never'),
                self.kv(method, what))

            # maybe?

        return self.run_vagrant(cmd, '--{cmd}-with'.format(**locals()), name)


    ## Additional API ##
    def init(self):
        """ Initialize Vagrantfile """
        self.info('Provision dir', self.provision_dir)

        # Are we resuming?
        if os.path.exists(self.vagrantfile) and os.path.isfile(self.vagrantfile):
            self.validate()
            return

        # Create a Vagrantfile
        self.create()

        # Let's add what's needed
        # Do this first to install provider
        self.add_how()

        # Add default entries to Vagrantfile
        self.add_defaults()

    def create(self):
        """ Create default Vagrantfile with our modifications """
        self.run_vagrant('init', '-fm', self.data['box'])
        self.info('Initialized new Vagrantfile', self.vf_read())

    def clean(self):
        """ remove box and base box """
        return self.run_vagrant('box', 'remove', '-', self.data['.format(**locals())box'])
        # TODO: libvirt storage removal?

    def validate(self):
        """ Validate Vagrantfile format """
        return self.run_vagrant('validate')

    def reload(self):
        """ restart guest machine """
        return self.run_vagrant('reload')

    def plugin_install(self, name):
        """ Install a vagrant plugin if it's not installed yet.
        """
        plugin = '{self.executable}-{name}'.format(**locals())
        command = ['plugin', 'install']
        try:
            # is it already present?
            return self.run("bash -c \".format(**locals()){self.executable} {command[0]} list | grep '^{plugin}'\"")
        except GeneralError:
            pass

        try:
            # try to install it
            return self.run_vagrant(command[0], command[1], plugin)
        except GeneralError as error:
            # Let's work-around the error handling limitation for now
            # by getting the output manually
            command = ' '.join([self.executable] + command + [plugin])

            out, err = self.run("bash -c \".format(**locals()){command}; :\"")

            if re.search(r"Conflicting dependency chains:", err) is None:
                raise error

            raise ConvertError('Dependency conflict detected.\n'
                    'Please install vagrant plugins from one source only(hint: `dnf remove vagrant-libvirt`).')

    ## Knowhow ##
    def check_how(self):
        """ Decide what to do when HOW is ...
            does not add anything into Vagrantfile yet
        """
        self.debug('VagrantProvider', 'Checking initial status, setting defaults.')

        self.set_default('how', 'virtual')
        self.set_default('image', self.default_image)

        image = self.data['image']

        if self.is_uri(image):
            self.set_default('box', 'box_' + self.instance_name)

            if re.search(r"\.box$", image) is None:
                # an actual box file, Great!
                pass

            elif re.search(r"\.qcow2$", image) is None:
                # do some qcow2 magic
                self.data['box'] = '...'
                raise SpecificationError("NYI: QCOW2 image")

            else:
                raise SpecificationError("Image format not recognized: {image}".format(**locals()))

        else:
            self.set_default('box', image)
            self.data['image'] = None

        for x in ('how', 'box', 'image'):
            self.info('    {x}'.format(**locals()), self.data[x])

    def add_how(self):
        """ Add provider (in Vagrant-speak) specifics """
        getattr(self,
            "how_{self.data['how']}".format(**locals()),
            lambda: 'generic',
            )()

    def how_virtual(self):
        self.debug("generating", "virtual")

        image = self.data['image']

        if image:
            self.add_config_value('vm', "box_url", image)

        # let's try libvirt as default for now
        self.how_libvirt()

    def how_generic():
        self.debug("generating", "generic")
        self.add_provider(self.data['how'])

    def how_libvirt(self):
        name = 'libvirt'
        self.debug("generating", name)

        self.plugin_install(name)

        self.add_provider(name, 'memory = 1024')
        self.vf_backup("QEMU session")
        try:
            self.add_provider(name, 'qemu_use_session = true')
        except GeneralError as error:
            # Not really an error
            #self.debug(error)
            self.vf_restore()

    def how_openstack(self):
        self.debug("generating", "openstack")
        raise SpecificationError('NYI: cannot currently run on openstack.')

    def how_docker(self):
        self.how_container()

    def how_podman(self):
        self.how_container()

    def how_container(self):
        self.debug("generating", "container")
        raise SpecificationError('NYI: cannot currently run containers.')


    ## END of API ##
    def vagrant_status(self):
        """ Get vagrant's status """
        raise ConvertError('NYI: cannot currently return status.')
        # TODO: how to get stdout from self.run?
        #csp = self.run_vagrant('status')
        #return self.hr(csp.stdout)

    def add_defaults(self):
        """ Adds default config entries
            1) Disable default sync
            2) To sync plan workdir
            3) setup ssh
            4) memory: 1024
        """
        self.add_synced_folder(".", "/vagrant", 'disabled: true')

        dir = self.step.plan.workdir
        self.add_synced_folder(dir, dir)

        self.add_config_value('ssh', 'username', "root")
        # probably not needed
        #self.add_config_value('ssh', 'insert_key', 'true')

        self.add_config_value('nfs', 'verify_installed', 'false')

    def run_vagrant(self, *args):
        """ Run vagrant command and raise an error if it fails

              args = 'command args'

            or

              args = ['comand', 'args']

        """
        if len(args) == 0:
            raise RuntimeError("vagrant has to run with args")
        elif len(args) == 1:
            args = args[0]

        cmd = self.prepend(args, self.executable)

#            timeout = self.timeout,
        return self.run(
            cmd,
            cwd = self.provision_dir)

    def add_synced_folder(self, sync_from, sync_to, *args):
        self.add_config('vm',
            'synced_folder',
            self.quote(sync_from),
            self.quote(sync_to),
            self.kv('type', self.sync_type),
            *args)

    def add_provider(self, provider, *config):
        self.add_config_block('provider', provider, *config)

    def add_config_block(self, name, block, *config):
        """ Add config block into Vagrantfile
        """
        config_str = ''
        for c in config:
            config_str += '{block}.{c}; '.format(**locals())

        self.add_config('vm', "{name} '{block}' do |{block}| {config_str}end".format(**locals()))

    def add_config_value(self, type, key, value):
        """ Add config = value into Vagrantfile
        """
        self.add_config(type, "{key} = '{value}'".format(**locals()))

    def add_config(self, type, *config):
        """ Add config entry into Vagrantfile right before last 'end',
            and prepends it with `config_prefix`.

            Adding arbitrary config entry:
                config = "string"

            or, with conversion:
                config = ['one', 'two', 'three']
                => one "two", three

        """
        if len(config) == 1:
            config = config[0]
        elif len(config) == 0:
            raise RuntimeError("config has no definition")
        else:
            config = '{config[0]} '.format(**locals()) + ', '.join(config[1:])

        self.info('Adding into Vagrantfile', "{type}.{config}".format(**locals()))

        vf_tmp = self.vf_read()

        # Lookup last 'end' in Vagrantfile
        i = 0
        for line in reversed(vf_tmp):
            i -= 1
            if (line.find('end') != -1):
                break

        vf_tmp = vf_tmp[:i] \
            + [self.config_prefix + "{type}.".format(**locals()) + config] \
            + vf_tmp[i:]

        self.vf_write(vf_tmp)

    def vf_read(self):
        """ read Vagrantfile
            also splits
        """
        return open(self.vagrantfile).read().splitlines()

    def vf_write(self, vf_tmp):
        """ write into Vagrantfile
            str or list
            runs validate()
        """
        if type(vf_tmp) is list:
            vf_tmp = self.eol.join(vf_tmp)

        with open(self.vagrantfile, 'w', newline=self.eol) as f:
            f.write(vf_tmp)

        self.validate()

    def vf_backup(self, msg=''):
        """ backup Vagrantfile contents to vf_data """
        if msg:
            self.info("Trying", msg)
        self.msg = msg
        self.vf_data = self.vf_read()

    def vf_restore(self):
        """ restore Vagrantfile contents frmo vf_data"""
        if self.msg:
            self.info('Reverting', self.msg, 'red')
            self.msg = ''
        self.vf_write(self.vf_data)


    ## Helpers ##
    def info(self, key = '', val = '', color = 'green'):
        """ info out!
            see msgout()
        """
        self.msgout('debug', key, val, color)

    def debug(self, key = '', val = '', color='yellow'):
        """ debugging, yay!
            see msgout()
        """
        self.msgout('debug', key, val, color)

    def msgout(self, mtype, key = '', val = '', color = 'red'):
        """ args: key, value, indent, color
            all optional
        """
        if type(val) is list and len(val):
            ind_val = ''
            for v in val:
                if v:
                    ind_val += ' '*self.default_indent + self.hr(v) + self.eol

            val = ind_val
        else:
            val = self.hr(val)

        emsg = lambda: RuntimeError("Message type unknown: {mtype}".format(**locals()))

        if val:
            getattr(self.super,
                mtype,
                emsg,
                )(key, val, color)
        else:
            getattr(self.super,
                mtype,
                emsg,
                )(key)

    def hr(self, val):
        """ return human readable data """
        if type(val) is tuple or type(val) is list:
            ret = ''
            for v in val:
                ret += self.hr(v)
            return ret

        if type(val) is bytes:
            val = str(val, "utf-8")

        elif type(val) is not str:
            val = str(val)

        try:
            val = rstrip(val)
            eol = self.eol
        except:
            eol = ''

        return '{val}{eol}'.format(**locals())

    def set_default(self, where, default):
        if not (where in self.data and self.data[where]):
            self.data[where] = default

    def prepend(self, thing, string):
        if type(thing) is list:
            return thing.insert(0, string)
        elif type(thing) is tuple:
            return (string ,) + thing
        else:
            return string + ' ' + thing

    def cmd_mkcp(self, target_dir, target):
        target_dir = self.quote(target_dir)
        target = self.quote(target)
        return 'mkdir -p {target_dir}; cp -vafr {target} {target_dir}'.format(**locals())

    def is_uri(self, uri):
        return getattr(urlparse(uri),
            'schema',
            None)

    def quote(self, string):
        return '"{string}"'.format(**locals())

    def kv(self, key, val):
        return '{key}: "{val}"'.format(**locals())
