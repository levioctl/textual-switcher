#!/usr/bin/python3 -u

# Note that running python with the `-u` flag is required on Windows,
# in order to ensure that stdin and stdout are opened in binary, rather
# than text, mode.

import os
import sys
import json
import time
import errno
import select
import struct
import traceback


logfile = open("/tmp/native-app-{}.log".format(os.getpid()), "w")
import time


def log(msg):
    logfile.write("{}: {}\n".format(time.ctime(), msg))
    logfile.flush()


class ExtensionMessages(object):
    @staticmethod
    def in_fd():
        return sys.stdin.fileno()

    # Encode a message for transmission, given its content.
    @staticmethod
    def _encode_message(msg_bytes):
        msg_str = msg_bytes.decode('utf-8')
        encoded_content = json.dumps(msg_str)
        encoded_length = struct.pack('@I', len(encoded_content))
        return {'length': encoded_length, 'content': encoded_content}

    # Send a message to stdout.
    @classmethod
    def send_message(cls, message):
        log("sending to app over pipe: {} bytes".format(len(message)))
        messaegs = message.split(b';')
        for msg_bytes in messaegs:
            msg_dict = cls._encode_message(msg_bytes)
            sys.stdout.buffer.write(msg_dict['length'])
            sys.stdout.write(msg_dict['content'])
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
        data = os.read(self._in_fifo, 2 ** 20)
        if len(data) == 0:
            # Writer closed
            return None
        return data

    def send_message(self, message):
        log("sending to switcher over pipe: {} bytes".format(len(message)))
        try:
            nr_bytes = os.write(self._out_fifo, message)
        except OSError as ex:
            if ex.errno == 32:
                raise DisconnectionException()
            else:
                log("cannot write to switcher, broken pipe (probably disconnected)")
                raise

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
        log(f'Creating out FIFO in "{fifo_path}"')
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


class DisconnectionEvent:
    def __init__(self, side):
        self.side = side


class DisconnectionException(Exception):
    def __init__(self, side=None, *args, **kwargs):
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
            while True:
                try:
                    events = self._wait_for_events()
                except IOError as ex:
                    if ex.errno == 4:
                        log("interrupted poll. will retry again in 5 seconds...")
                        time.sleep(5)
                        continue
                    else:
                        raise ex
                break
            for event in events:
                if isinstance(event, DisconnectionEvent):
                    raise DisconnectionException(event.side)
                elif isinstance(event, Message):
                    self._route_message(event)
                else:
                    assert False

    def _route_message(self, message):
        destination = self._sides['b'] if message.source == self._sides['a'] else self._sides['a']
        try:
            destination.send_message(message.content)
        except DisconnectionException:
            raise DisconnectionException(side=destination)

    def _wait_for_events(self):
        events = list()
        for fd, event_type in self._epoll.poll():
            source = self._sides['a'] if fd == self._sides['a'].in_fd() else self._sides['b']
            if event_type in (select.EPOLLIN, select.EPOLLRDNORM):
                content = os.read(fd, 2 ** 20)
                message = Message(content=content, source=source)
                events.append(message)
            elif event_type == select.EPOLLHUP:
                events.append(DisconnectionEvent(side=source))
            else:
                continue

        return events


def main():
    log("Starting...")
    extension_messages = ExtensionMessages()
    switcher_messages = SwitcherMessages()
    messageSwitch = PointToPointPipesSwitch(a=extension_messages, b=switcher_messages)
    run_another_iteration = True
    while run_another_iteration:
        log("Running another iteration")
        run_another_iteration = False
        try:
            messageSwitch.run()
        except DisconnectionException as ex:
            log("Disconnected. Handling...")
            if ex.side == switcher_messages:
                log("Switcher disconnected. Reconnecting...")
                ex.side.reconnect()
                log("Reconnected.")
                messageSwitch = PointToPointPipesSwitch(a=extension_messages, b=switcher_messages)
                run_another_iteration = True
        except Exception as ex:
            log("Exception: {}".format(ex))
            tb = "".join(traceback.format_exc())
            log(tb)
        finally:
            log("Cleaning up...")
            if not run_another_iteration:
                switcher_messages.cleanup()
            log("Clean up done.")


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        log("Exception while reconnecting: {}".format(ex))
