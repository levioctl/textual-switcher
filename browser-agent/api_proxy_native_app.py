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


class ExtensionMessages(object):
    @staticmethod
    def in_fd():
        return sys.stdin.fileno()

    # Encode a message for transmission, given its content.
    @staticmethod
    def _encode_message(message_content):
        encoded_content = json.dumps(message_content)
        encoded_length = struct.pack('@I', len(encoded_content))
        return {'length': encoded_length, 'content': encoded_content}

    # Send a message to stdout.
    @classmethod
    def send_message(cls, message):
        messaegs = message.split(';')
        for message in messaegs:
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

    def get_message(self):
        data = os.read(self._in_fifo, 2 ** 10)
        if len(data) == 0:
            # Writer closed
            return None
        return data

    def send_message(self, message):
        nr_bytes = os.write(self._out_fifo, message)

    def in_fd(self):
        return self._in_fifo

    def reconnect(self):
        self.cleanup()
        self._connect()

    def _connect(self):
        self._in_fifo = self._open_in_fifo()
        try:
            self._out_fifo = self._open_out_fifo()
        except:
            self.cleanup()
            raise

    def _validate_fifo_dir_exists(self):
        try:
            os.makedirs(self.FIFO_PATH_DIR)
        except OSError as ex:
            if ex.errno != errno.EEXIST:
                raise

    def _open_in_fifo(self):
        self._create_fifo(self._in_fifo_filename)
        fd = os.open(self._in_fifo_filename, os.O_RDONLY | os.O_NONBLOCK)
        return fd

    def _open_out_fifo(self):
        self._create_fifo(self._out_fifo_filename)
        fd = os.open(self._out_fifo_filename, os.O_WRONLY)
        return fd

    @staticmethod
    def _create_fifo(fifo_path):
        try:
            os.mkfifo(fifo_path)
        except OSError as ex:
            if ex.errno != errno.EEXIST:
                raise

    def cleanup(self):
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
        self._epoll.register(self._sides['a'].in_fd())
        self._epoll.register(self._sides['b'].in_fd())

    def run(self):
        while True:
            events = self._wait_for_events()
            for event in events:
                if isinstance(event, Disconnection):
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
        for fd, event_type in self._epoll.poll():
            source = self._sides['a'] if fd == self._sides['a'].in_fd() else self._sides['b']
            if event_type in (select.EPOLLIN, select.EPOLLRDNORM):
                content = os.read(fd, 2 ** 10)
                message = Message(content=content, source=source)
                events.append(message)
            elif event_type == select.EPOLLHUP:
                events.append(Disconnection(side=source))
            else:
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
                ex.side.reconnect()
                messageSwitch = PointToPointPipesSwitch(a=extension_messages, b=switcher_messages)
                run_another_iteration = True
        except Exception as ex:
            pass
        finally:
            if not run_another_iteration:
                switcher_messages.cleanup()


if __name__ == "__main__":
    main()
