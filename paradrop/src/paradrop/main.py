'''
Core module. Contains the entry point into Paradrop and establishes all other modules.
Does not implement any behavior itself.
'''

import argparse
import signal

from twisted.internet import reactor, defer
from autobahn.twisted.wamp import ApplicationRunner

from paradrop.base import output, nexus, cxbr, settings
from paradrop.backend import apiinternal


class Nexus(nexus.NexusBase):

    def __init__(self):
        # Want to change logging functionality? See optional args on the base class and pass them here
        super(Nexus, self).__init__(stealStdio=True, printToConsole=True)

    def onStart(self):
        super(Nexus, self).onStart()

        # onStart is called when the reactor starts, not when the connection is made.
        # Check for provisioning keys and attempt to connect
        if not self.provisioned():
            output.out.warn('Router has no keys or identity. Waiting to connect to to server.')
        else:
            return self.connect(apiinternal.RouterSession)

    def onStop(self):
        # if self.session is not None:
        #     self.session.leave()
        # else:
        #     print 'No session found!'

        super(Nexus, self).onStop()


def main():
    p = argparse.ArgumentParser(description='Paradrop daemon running on client')
    p.add_argument('--config', help='Run as the configuration daemon',
                   action='store_true')
    p.add_argument('--mode', '-m', help='Set the mode to one of [production, local, unittest]',
                   action='store', type=str, default='production')
    p.add_argument('--portal', '-p', help='Set the folder of files for local portal',
                   action='store', type=str)
    p.add_argument('--no-exec', help='Skip execution of configuration commands',
                   action='store_false', dest='execute')

    p.add_argument('--verbose', '-v', help='Enable verbose', action='store_true')

    args = p.parse_args()
    # print args

    settings.loadSettings(args.mode, [])

    # Globally assign the nexus object so anyone else can access it.
    # Sorry, programming gods. If it makes you feel better this class
    # replaces about half a dozen singletons
    nexus.core = Nexus()

    if args.config:
        from paradrop import confd

        # Start the configuration daemon
        confd.main.run_pdconfd(dbus=False)

    else:
        from paradrop import confd
        from paradrop.backend import server
        from paradrop.lib.misc.reporting import sendStateReport
        from paradrop.backend.apibridge import updateManager

        pdid = nexus.core.info.pdid
        apitoken = nexus.core.getKey('apitoken')
        isProvisioned = (pdid is not None \
            and apitoken is not None)

        if isProvisioned:
            # Set up communication with pdserver.
            # 1. Create a report of the current system state and send that.
            # 2. Poll for a list of updates that should be applied.
            sendStateReport()
            updateManager.startUpdate()

        # Start the configuration service as a thread
        confd.main.run_thread(execute=args.execute, dbus=False)

        if args.mode != "unittest":
            from paradrop.backend.portal import startPortal
            if args.portal:
                startPortal(args.portal)
            else:
                startPortal()

        # Now setup the RESTful API server for Paradrop
        server.setup(args)


if __name__ == "__main__":
    main()