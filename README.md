# log2XMPP

`log2XMPP` aims to forward syslog messages (received on an Unix socket) to a
XMPP chatroom.

Main advantages over other tools like `logcheck` are that:

  - you are notified in realtime (you don't have to wait for the next
    hourly/daily email report)
  - your mailbox will not be filled by hundreds of spammy redundant email with
    the `unread` flag anymore if you don't read them for a week. It is easier
    to take a quick look at a one message per line chatroom backlog than to
    open each email to read its content
  - you can use syslog filters to forward only _ERROR_ message level, or only
    _auth_ facility
  - sending log messages in emails can be insecure and leak sensitive
    informations unless a) you have denied cleartext SMTP on your mail server
    and b) you don't use a third party email provider that you couldn't trust.

## Installation

`log2XMPP` requires `pyhton-sleekxmpp` and `python-daemon`.
On a Debian stable machine, install them with:
```
# apt install pyhton-sleekxmpp python-daemon
```

Then put `log2xmpp.py` somewhere on your hierarchy (for example in _/usr/local/bin/_).

## `rsyslog` configuration

To make `rsyslog` send its log to an external Unix socket, you must load the [omuxsock](http://www.rsyslog.com/doc/v7-stable/configuration/modules/omuxsock.html) module:
```
module(load="omuxsock")
$OMUxSockSocket /var/run/log2xmpp/syslog.sock
```

Then, add a rule to forward messages to it:

  - all messages:
    ```
    *.* :omuxsock:
    ```
  - only `auth` and `authpriv` facility:
    ```
    auth,authpriv.* :omuxsock:
    ```
  - [and so on](http://www.rsyslog.com/doc/v7-stable/index.html)…

Also if you use to used `logcheck` to filtering out your log, `log2XMPP` can read `logcheck`'s ignore rules in an arbitrary directory (but defaults to _/etc/logcheck/ignore.d.server/_) with `--logcheck-filters` option.

## Run it

```
$ ./log2xmpp.py --help
usage: log2xmpp.py [-h] --jid JID [--jid-password PASS] --room ROOM
                   [--room-password ROOM_PASSWORD] [--syslog [SYSLOG_SOCKET]]
                   [--logcheck-filters [LOGCHECK_FILTERS]]
                   [-d {DEBUG,INFO,WARNING,ERROR,CRITICAL}] [-p PID]

Listen on unix socket and send syslog messages to XMPP chatroom.

optional arguments:
  -h, --help            show this help message and exit
  --jid JID             JID to use
  --jid-password PASS   JID password
  --room ROOM           XMPP chatroom to join
  --room-password ROOM_PASSWORD
                        optional chatroom password
  --syslog [SYSLOG_SOCKET]
                        listen on unix socket to syslog messages
  --logcheck-filters [LOGCHECK_FILTERS]
                        Use logcheck ignore filters
  -d {DEBUG,INFO,WARNING,ERROR,CRITICAL}, --debug {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        debug level
  -p PID, --pid PID     PID file
```

If not specified on the command line, JID password and optional ROOM password are read from environment variables _JID_PASSWORD_ and _ROOM_PASSWORD_.

```
$ JID_PASSWORD='a secrete password' ./log2xmpp.py --jid log2xmpp@example.net --room sysadmin@chat.example.net -p /var/run/log2xmpp/log2xmpp.pid --syslog /var/run/log2xmpp/syslog.sock --logcheck-filters
```

TODO: create a systemd unit and a dedicated system user with permisions on _/var/run/log2xmpp/_.
