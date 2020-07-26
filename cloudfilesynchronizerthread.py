import os
import time
import Queue
import threading
import traceback
import gdrive_client


class CloudFileSynchronizerThread(threading.Thread):
    LOCAL_DIR = os.path.expanduser("~/.config/textual-switcher")

    def __init__(self, filename, connected_callback, disconnected_callback, get_contents_callback):
        self._filename = filename
        self._connected_callback = connected_callback
        self._disconnected_callback = disconnected_callback
        self._get_contents_callback = get_contents_callback
        self._content = None
        self._cloud_file_synchronizer = None
        self._incoming_requests = Queue.Queue()
        super(CloudFileSynchronizerThread, self).__init__()
        self.daemon = True
        self.start()

    def run(self):
        while True:
            # Connect if needed
            if not self._is_connected():
                try:
                    self._connect()
                except:
                    print("Could not connect to cloud storage: {}".format(traceback.format_exc()))
                    
                    time.sleep(10)
                    continue

                # Inform main loop that connection is established
                self._connected_callback()

            # Listen to requests
            try:
                request = self._incoming_requests.get(block=True)
                if request['type'] == 'write':
                    filename = os.path.join(self.LOCAL_DIR, self._filename)
                    with open(self._filename, "w") as local_file:
                        local_file.write(request['contents'])

                    print("Writing to cloud once")
                    self._cloud_file_synchronizer.write_to_remote_file()
                elif request['type'] == 'read':
                    contents = self._cloud_file_synchronizer.read_remote_file()
                    self._get_contents_callback(contents)
            except Exception as ex:
                print("Cloud connection failed: {}".format(traceback.format_exc()))
                self._disconnected_callback()

    def _is_connected(self):
        return self._cloud_file_synchronizer is not None

    def async_get_content(self):
        self._incoming_requests.put({'type': 'read'}, block=True)

    def async_write_to_cloud(self, contents):
        self._incoming_requests.put({'type': 'write', 'contents': contents}, block=True)

    def _connect(self):
        self._cloud_file_synchronizer = gdrive_client.GoogleDriveFileSynchronizer(self._filename,
                                                                     create_if_does_not_exist=True)
