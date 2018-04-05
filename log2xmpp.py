#!/usr/bin/env python3
#
# log2xmpp: listen on unix socket and send syslog messages to a chatroom.
# Copyright (C) 2018  Romain Dessort <romain@univers-libre.net>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import daemon
import lockfile
import signal
import logging
import socket
import sys
import os
import regex
import sleekxmpp
import argparse


class XmppBot(sleekxmpp.ClientXMPP):

    def __init__(self, jid, password, room, room_password=None):
        sleekxmpp.ClientXMPP.__init__(self, jid, password)

        self.room = room
        self.room_password = room_password
        self.nick = 'Log2XMPP'

        self.add_event_handler("session_start", self.session_start)

        self.register_plugin('xep_0030') # Service Discovery
        self.register_plugin('xep_0199') # XMPP Ping
        self.register_plugin('xep_0045') # Multi-User Chat

    def session_start(self, event):
        self.send_presence()
        self.get_roster()

        # Join the room.
        self.plugin['xep_0045'].joinMUC(self.room,
                self.nick,
                password=self.room_password,
                wait=False)

    def post_message(self, message):
        self.send_message(mto=self.room, mbody=message, mtype='groupchat')


class Log2xmpp:

    def __init__(self, args):
        self.logging = None
        self.syslog_socket = args.syslog_socket
        self.logcheck_filters = args.logcheck_filters
        self.xmppbot = XmppBot(args.jid, args.jid_password, args.room,
                args.room_password)

    def main_loop(self):
        self.logging.info('Starting XMPP client')
        if not self.xmppbot.connect():
            self.logging.error('Unable to connect to XMPP server')
            sys.exit(2)
        self.xmppbot.process(block=False)

        if self.syslog_socket:
            self.logging.info('Listening on {}'.format(self.syslog_socket))
            if os.path.exists(self.syslog_socket):
                os.remove(self.syslog_socket)
            self.syslog_sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            self.syslog_sock.bind(self.syslog_socket)

            if self.logcheck_filters:
                self.logging.info('Reading logcheck ignore filters in {}'
                        .format(self.logcheck_filters))
                logcheck_regexp_lines = []
                for file in os.listdir(self.logcheck_filters):
                    file = os.path.join(self.logcheck_filters, file)
                    if os.path.isfile(file):
                        with open(file, 'r') as f:
                            logcheck_regexp_lines.extend([line.rstrip() for line in f])

                logcheck_regexps = list(map(regex.compile, logcheck_regexp_lines))

        while True:
            if self.syslog_socket:
                data, addr = self.syslog_sock.recvfrom(1024)
                if not data:
                    break
                self.logging.debug('Recieved data: %s' % data)
                syslog_line = data[4:].decode("utf-8").rstrip()

                ignore_line = False
                if self.logcheck_filters:
                    for regexp in logcheck_regexps:
                        if regexp.search(syslog_line):
                            self.logging.debug(
                                    'Line "{}" matches logcheck regexp "{}", ignoring line'
                                    .format(syslog_line, regexp.pattern))
                            ignore_line = True
                            break

                if not ignore_line:
                    self.logging.debug('Sending line "{}" to chatroom'
                        .format(syslog_line))
                    self.xmppbot.post_message(syslog_line)
            else:
                break

    def program_cleanup(self, signum, frame):
        self.logging.info('Signal {} received, terminating'.format(signum))
        self.logging.info('Closing socket {}'.format(self.syslog_socket))
        self.syslog_sock.close()
        os.remove(self.syslog_socket)
        self.logging.info('Disconnecting from XMPP chatroom')
        self.xmppbot.disconnect(wait=True)
        self.logging.shutdown()


if __name__ == '__main__':

    # Parse arguments.
    parser = argparse.ArgumentParser(
            description='Listen on unix socket and send syslog messages to \
                    XMPP chatroom.')
    parser.add_argument('--jid', help='JID to use', required=True)
    parser.add_argument('--jid-password', help='JID password', metavar='PASS')
    parser.add_argument('--room', help='XMPP chatroom to join', required=True)
    parser.add_argument('--room-password', help='optional chatroom password')
    parser.add_argument('--syslog',
            help='listen on unix socket to syslog messages',
            nargs='?', const='/var/run/log2xmpp.sock', dest='syslog_socket')
    parser.add_argument('--logcheck-filters',
            help='Use logcheck ignore filters', nargs='?',
            const='/etc/logcheck/ignore.d.server/')
    parser.add_argument('-d', '--debug', help='debug level',
            choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
    parser.add_argument('-p', '--pid', help='PID file',
            default='/var/run/log2xmpp.pid')
    args = parser.parse_args()

    # Read JID_PASSWORD and ROOM_PASSWORD environment variables if not specified
    # on the command line.
    if not args.jid_password:
        if 'JID_PASSWORD' in os.environ:
            args.jid_password = os.environ['JID_PASSWORD']
        else:
            parser.print_usage()
            print('error: neither --jid-password and JID_PASSWORD is specified')
            sys.exit(2)
    if not args.room_password:
        if 'ROOM_PASSWORD' in os.environ:
            args.room_password = os.environ['ROOM_PASSWORD']

    log2xmpp = Log2xmpp(args)

    # Setup daemon context and daemonize.
    context = daemon.DaemonContext(
        pidfile = lockfile.FileLock(args.pid),
        detach_process = False,
        signal_map = {
            signal.SIGTERM: log2xmpp.program_cleanup,
        },
        stdout = sys.stdout,
        stderr = sys.stderr,
    )

    with context:
        # Setup logging.
        logging.basicConfig(level=args.debug,
                format='%(levelname)s: [%(name)s] %(message)s')
        log2xmpp.logging = logging

        logging.info('Daemon started')
        log2xmpp.main_loop()
