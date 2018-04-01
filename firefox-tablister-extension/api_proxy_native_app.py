#!/usr/bin/python -u

# Note that running python with the `-u` flag is required on Windows,
# in order to ensure that stdin and stdout are opened in binary, rather
# than text, mode.

import os
import sys
import json
import errno
import select
import struct


def log(message):
    import time
    with open('/tmp/proxy.log', 'a') as f:
        f.write(str(os.getpid()) + ': ' + time.ctime() + ': ' + str(message) + '\n')


class ExtensionMessages(object):
    @staticmethod
    def in_fd():
        return sys.stdin.fileno()

    # Read a message from stdin and decode it.
    @staticmethod
    def parse_message(message):
        messages = list()
        while message:
            raw_length = message[:4]
            message = message[4:]
            if not raw_length:
                sys.exit(0)
            message_length = struct.unpack('@I', raw_length)[0]
            message = message_length[4:4 + raw_length]
            messages.append(message)

    # Encode a message for transmission, given its content.
    @staticmethod
    def _encode_message(message_content):
        encoded_content = json.dumps(message_content)
        encoded_length = struct.pack('@I', len(encoded_content))
        return {'length': encoded_length, 'content': encoded_content}


    # Send a message to stdout.
    @classmethod
    def send_message(cls, message):
        log('sending message to extension')
        message = cls._encode_message(message)
        sys.stdout.write(message['length'])
        sys.stdout.write(message['content'])
        sys.stdout.flush()


class SwitcherMessages(object):
    UID = os.getuid()
    FIFO_PATH_DIR = os.path.join("/run", "user", str(UID), "textual-switcher-proxy")
    PPID = os.getppid()
    IN_FIFO_FILENAME = "textual_switcher_to_api_proxy_for_firefox_pid_%d" % (PPID,)
    OUT_FIFO_FILENAME = "api_proxy_to_textual_switcher_for_firefox_pid_%d" % (PPID,)

    def __init__(self):
        self._validate_fifo_dir_exists()
        self._in_fifo_filename = os.path.join(self.FIFO_PATH_DIR, self.IN_FIFO_FILENAME)
        self._out_fifo_filename = os.path.join(self.FIFO_PATH_DIR, self.OUT_FIFO_FILENAME)
        self._in_fifo = None
        self._connect()
        log('done')

    def get_message(self):
        log('reading data')
        data = os.read(self._in_fifo, 4096)
        log('data read')
        if len(data) == 0:
            log('data is empty')
            # Writer closed
            return None
        return data

    def send_message(self, message):
        log('sending data to switcher')
        nr_bytes = os.write(self._out_fifo, message)
        log('bytes sent: ' + str(nr_bytes))

    def in_fd(self):
        return self._in_fifo

    def reconnect(self):
        self.cleanup()
        self._connect()

    def _connect(self):
        log('opening in fifo...')
        self._in_fifo = self._open_in_fifo()
        log('opening out fifo...')
        try:
            self._out_fifo = self._open_out_fifo()
        except:
            log('error opening out fifo')
            self.cleanup()
            raise

    def _validate_fifo_dir_exists(self):
        try:
            os.makedirs(self.FIFO_PATH_DIR)
        except OSError as ex:
            if ex.errno != errno.EEXIST:
                raise

    def _open_in_fifo(self):
        log('creating in fifo')
        self._create_fifo(self._in_fifo_filename)
        log('opening in fifo...' + self._in_fifo_filename)
        fd = os.open(self._in_fifo_filename, os.O_RDONLY | os.O_NONBLOCK)
        log('in fifo open.')
        return fd

    def _open_out_fifo(self):
        log('creating out fifo')
        self._create_fifo(self._out_fifo_filename)
        log('opening out fifo ' + self._out_fifo_filename)
        fd = os.open(self._out_fifo_filename, os.O_WRONLY)
        log('out fifo open.')
        return fd

    @staticmethod
    def _create_fifo(fifo_path):
        log('3')
        try:
            os.mkfifo(fifo_path)
        except OSError as ex:
            log('4')
            if ex.errno != errno.EEXIST:
                raise
            log('fifo already exists.')

    def cleanup(self):
        log('cleaning...')
        try:
            os.close(self._in_fifo)
        except:
            pass
        try:
            os.close(self._out_fifo)
        except:
            pass
        try:
            os.unlink(self._in_fifo_filename)
        except:
            pass
        try:
            os.unlink(self._out_fifo_filename)
        except:
            pass

class Message(object):
    def __init__(self, content, source):
        self.content = content
        self.source = source


class Disconnection(Exception):
    def __init__(self, side):
        self.side = side


class DisconnectionException(Exception):
    def __init__(self, side, *args, **kwargs):
        self.side = side
        super(DisconnectionException, self).__init__(*args, **kwargs)


class PointToPointPipesSwitch(object):
    def __init__(self, a, b):
        self._sides = dict(a=a, b=b)
        self._epoll = select.epoll()
        log('registering...')
        self._epoll.register(self._sides['a'].in_fd())
        self._epoll.register(self._sides['b'].in_fd())

    def run(self):
        while True:
            log('waiting for messages...')
            events = self._wait_for_events()
            for event in events:
                if isinstance(event, Disconnection):
                    log('Side %s has disconnected.' % (event.side,))
                    raise DisconnectionException(event.side)
                elif isinstance(event, Message):
                    self._route_message(event)
                else:
                    assert False

    def _route_message(self, message):
        if message.source == self._sides['a']:
            destination = self._sides['b']
        else:
            destination = self._sides['a']
        destination.send_message(message.content)

    def _wait_for_events(self):
        events = list()
        log('polling...')
        for fd, event_type in self._epoll.poll():
            source = self._sides['a'] if fd == self._sides['a'].in_fd() else self._sides['b']
            if event_type in (select.EPOLLIN, select.EPOLLRDNORM):
                log('message ready from ' +  str(source) + '. Reading...')
                content = os.read(fd, 4096)
                log('Read done: ')
                message = Message(content=content, source=source)
                events.append(message)
            elif event_type == select.EPOLLHUP:
                events.append(Disconnection(side=source))
            else:
                log('bad event from fd '  +  str(fd) + ' of type ' +  str(event_type))
                continue

        return events


def main():
    extension_messages = ExtensionMessages()
    switcher_messages = SwitcherMessages()
    messageSwitch = PointToPointPipesSwitch(a=extension_messages, b=switcher_messages)
    run_another_iteration = True
    while run_another_iteration:
        run_another_iteration = False
        try:
            messageSwitch.run()
        except DisconnectionException as ex:
            if ex.side == switcher_messages:
                log('Reconnecting...')
                ex.side.reconnect()
                log('Reconnected. Creating switch...')
                messageSwitch = PointToPointPipesSwitch(a=extension_messages, b=switcher_messages)
                log('Switch ready. Running switch...')
                run_another_iteration = True
        except Exception as ex:
            log('exception ', str(ex))
        finally:
            if not run_another_iteration:
                switcher_messages.cleanup()
                log('DONE!!!')


if __name__ == "__main__":
    main()
