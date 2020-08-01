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
                 write_callback):
        self._filename = filename
        self._connected_callback = connected_callback
        self._disconnected_callback = disconnected_callback
        self._get_contents_callback = get_contents_callback
        self._get_local_cache_callback = get_local_cache_callback
        self._write_callback = write_callback
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
                    with open(self._filename, "w") as local_file:
                        local_file.write(request['contents'])

                    print("Writing to cloud once")
                    self._cloud_file_synchronizer.write_to_remote_file()
                    self._write_callback()
                elif request['type'] == 'read':
                    contents = self._cloud_file_synchronizer.read_remote_file()
                    self._get_contents_callback(contents)

                elif request['type'] == 'read_cache':
                    try:
                        with open(self._filename) as local_file:
                            contents = local_file.read()
                        self._get_local_cache_callback(contents)
                    except:
                        print("Could not read bookmarks from local cache: {}".format(traceback.format_exc()))
            except Exception as ex:
                print("Cloud connection failed: {}".format(traceback.format_exc()))
                self._disconnected_callback()

    def _is_connected(self):
        return self._cloud_file_synchronizer is not None

    def async_read(self):
        self._incoming_requests.put({'type': 'read'}, block=True)

    def async_write(self, contents):
        self._incoming_requests.put({'type': 'write', 'contents': contents}, block=True)

    def async_read_local_cache(self):
        self._incoming_requests.put({'type': 'read_cache'}, block=True)

    def _connect(self):
        self._cloud_file_synchronizer = gdrive_client.GoogleDriveFileSynchronizer(self._filename,
                                                                     create_if_does_not_exist=True)
