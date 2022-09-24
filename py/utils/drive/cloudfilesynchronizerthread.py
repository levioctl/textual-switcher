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
        self._local_cache_contents = None
        self._gdrive_client = gdrive_client.GoogleDriveClient()
        self._cloud_file_synchronizer = gdrive_client.GoogleDriveFileSynchronizer(self._filename,
            self._gdrive_client)
        self._user_invoked_browser_authentication = threading.Event()
        self._sync_status = 'idle'
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
        self._local_cache_contents = None
        try:
            with open(self._filename) as local_file:
                self._local_cache_contents = local_file.read()
        except IOError as ex:
            if ex.errno == 2:
                print("Local cache does not exist.")
            else:
                print("Could not read bookmarks from local cache: {}".format(traceback.format_exc()))

        return self._local_cache_contents

    def async_read(self):
        self._incoming_requests.put({'type': 'read-cache'}, block=True)
        self._incoming_requests.put({'type': 'read'}, block=True)

    def async_write(self, contents):
        self._incoming_requests.put({'type': 'write', 'contents': contents}, block=True)

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

        self._sync_status = 'connected-but-unknown'

    def _write_local_cache(self, contents):
        print('Writing to local cache')
        with open(self._filename, "w") as local_file:
            local_file.write(request['contents'])
        self._local_cache_contents = contents

    def _write_to_cloud(self, contents):
        print("Writing to cloud once")
        self._cloud_file_synchronizer.write_to_remote_file()

    def _serve_requests(self):
        try:
            request = self._incoming_requests.get(block=True)
            if request['type'] == 'write':
                self._write_local_cache(contents=request['contents'])
                self._write_to_cloud(contents=request['contents'])
                self._write_callback()

            elif request['type'] == 'read':
                # Read local cache and cloud file
                self._read_cache_once()
                cloud_file_contents = self._cloud_file_synchronizer.read_remote_file()

                # Make booleans for convneience
                cloud_file_exists = cloud_file_contents is not None
                local_cache_exists = self._local_cache_contents is not None

                # Both exist and are equal - return contents
                if (cloud_file_contents == self._local_cache_contents and local_cache_exists
                        and cloud_file_exists):
                    self._get_contents_callback(contents)

                # Local cache doesn't exist, cloud file does exist - create local cache
                elif cloud_file_exists and not local_cache_exists:
                    self._write_local_cache(contents=cloud_file_contents)
                    self._get_contents_callback(contents)

                # cloud file doesn't exist, local cache exists - return cache and write to cloud
                elif not cloud_file_exists and local_cache_exists:
                    # Provide the local cache first
                    self._get_local_cache_callback(self._local_cache_contents)

                    # Write to cloud file
                    self._write_to_cloud(contents=cloud_file_contents)

                # Both exist and are different
                elif cloud_file_contents is not None and self._local_cache_contents is not None:
                    raise Exception('implement me')

                elif cloud_file_contents is None and self._local_cache_contents is None:
                    raise Exception('implement me')

                else:
                    assert False, 'huh'

            elif request['type'] == 'read-cache':
                self._read_cache_once()
                if self._local_cache_contents is not None:
                    self._get_local_cache_callback(self._local_cache_contents)

        except Exception as ex:
            print("Cloud connection failed: {}".format(traceback.format_exc()))
            self._disconnected_callback()
