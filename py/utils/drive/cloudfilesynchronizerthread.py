import threading
import os
import time
import traceback
import queue
import threading
import traceback

from utils.drive import gdrive_client


class CloudFileSynchronizerThread(threading.Thread):
    def __init__(self,
                 filename,
                 connected_callback,
                 disconnected_callback,
                 get_contents_callback,
                 get_local_cache_callback,
                 browser_authentication_needed,
                 write_callback):
        self._filename = filename
        self._external_connected_callback = connected_callback
        self._disconnected_callback = disconnected_callback
        self._get_contents_callback = get_contents_callback
        self._get_local_cache_callback = get_local_cache_callback
        self._browser_authentication_needed = browser_authentication_needed
        self._write_callback = write_callback
        self._content = None
        self._cloud_file_synchronizer = None
        self._incoming_requests = queue.Queue()
        self._local_cache = None
        self._gdrive_client = gdrive_client.GoogleDriveClient()
        self._cloud_file_synchronizer = gdrive_client.GoogleDriveFileSynchronizer(self._filename,
            self._gdrive_client)
        self._user_invoked_browser_authentication = threading.Event()
        super().__init__()
        self.daemon = True

    def is_connected_to_drive(self):
        return self._gdrive_client.is_connected()

    def run(self):
        while True:
            self.run_once()

    def run_once(self):
        # Connecte if not connected
        if not self._gdrive_client.is_connected():
            self._connect()

            # Inform caller that connection is established
            self._external_connected_callback()

        # Listen and serve request
        self._serve_requests()

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
        self._user_invoked_browser_authentication.set()

    def _connect(self):
        try:
            # Try connecting with local token
            self._gdrive_client.connect_with_local_token()
        except gdrive_client.LocalTokenInvalid__ShouldTryRefreshWithBrowserException:
            # Not authenticated by local credentials, wait for user to actively invoke
            # authentication process using the webbrowser

            # First, Tell the user that explicit authentication is needed
            self._browser_authentication_needed()
            print('Connected with local token')

            # Wait for user to approve browser authentication flow
            print("Waiting for user to order explicit authentication")
            self._user_invoked_browser_authentication.wait()

            # User invoked an explicit auth. request. Do it
            print("Fetching credentials explicitly...")
            self._gdrive_client.connect_with_browser()
            print("Now connected.")

    def _serve_requests(self):
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
