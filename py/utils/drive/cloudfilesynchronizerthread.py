import threading
import os
import time
import traceback
import Queue
import threading
import traceback
import gdrive_client


class CloudFileSynchronizerThread(threading.Thread):
    LOCAL_DIR = os.path.expanduser("~/.config/textual-switcher")

    def __init__(self,
                 filename,
                 connected_callback,
                 disconnected_callback,
                 get_contents_callback,
                 get_local_cache_callback,
                 authentication_needed_callback,
                 write_callback):
        self._filename = filename
        self._external_connected_callback = connected_callback
        self._disconnected_callback = disconnected_callback
        self._get_contents_callback = get_contents_callback
        self._get_local_cache_callback = get_local_cache_callback
        self._authentication_needed_callback = authentication_needed_callback
        self._write_callback = write_callback
        self._content = None
        self._cloud_file_synchronizer = None
        self._incoming_requests = Queue.Queue()
        self._local_cache = None
        self._cloud_file_synchronizer = gdrive_client.GoogleDriveFileSynchronizer(self._filename,
                                                                     self._connected_callback,
                                                                     create_if_does_not_exist=True)
        self._user_invoked_explicit_authentication_event = threading.Event()
        self._connected_callback_event = threading.Event()
        super(CloudFileSynchronizerThread, self).__init__()
        self.daemon = True

    def is_connected_to_drive(self):
        return self._cloud_file_synchronizer.is_authenticated()

    def run(self):
        contents = self._read_cache_once()
        if contents is not None:
            self._get_local_cache_callback(contents)

        while True:
            # If not authenticated by local credentials, wait for user to actively invoke
            # authentication process using the webbrowser
            while not self._cloud_file_synchronizer.is_authenticated():
                # Tell the user that explicit authentication is needd
                self._authentication_needed_callback()
                # Wait for authentication event
                print("Waiting for user to order explicit authentication")
                self._user_invoked_explicit_authentication_event.wait()
                # User invoked an explicit auth. request. Do it
                print("Fetching credentials explicitly...")
                self._cloud_file_synchronizer.try_to_authenticate_explicitly()
                # Wait until authenticated, before listening for commands
                print("Waiting for explicit authentication...")
                self._connected_callback_event.wait()
                print("Now connected.")

            # Inform main loop that connection is established
            self._external_connected_callback()

            # Listen to requests
            try:
                request = self._incoming_requests.get(block=True)
                if request['type'] == 'write':
                    with open(self._filename, "w") as local_file:
                        local_file.write(request['contents'])

                    print("Writing to cloud once")
                    self._cloud_file_synchronizer.write_to_remote_file()
                    self._write_callback()
                elif request['type'] == 'read':
                    contents = self._cloud_file_synchronizer.read_remote_file()
                    self._get_contents_callback(contents)
                elif request['type'] == 'read_cache':
                    contents = self._read_cache_once()
                    if contents is not None:
                        self._get_local_cache_callback(contents)
            except Exception as ex:
                print("Cloud connection failed: {}".format(traceback.format_exc()))
                self._disconnected_callback()

    def _connected_callback(self):
        self._connected_callback_event.set()

    def _read_cache_once(self):
        print("Reading local cache...")
        contents = None
        try:
            with open(self._filename) as local_file:
                contents = local_file.read()
        except IOError as ex:
            if ex.errno == 2:
                print("Local cache does not exist.")
            else:
                print("Could not read bookmarks from local cache: {}".format(traceback.format_exc()))
        else:
            print("Could not read bookmarks from local cache: {}".format(traceback.format_exc()))

        return contents

    def async_read(self):
        self._incoming_requests.put({'type': 'read'}, block=True)

    def async_write(self, contents):
        self._incoming_requests.put({'type': 'write', 'contents': contents}, block=True)

    def async_read_local_cache(self):
        self._incoming_requests.put({'type': 'read_cache'}, block=True)

    def get_current_cache(self):
        return self._local_cache

    def try_to_connect_explicitly(self):
        self._user_invoked_explicit_authentication_event.set()
