import unittest
from unittest import mock
import os
import yaml

from utils import bookmark_store
from utils.drive import cloudfilesynchronizerthread, gdrive_client


class FakeCloudFileSyncThread(cloudfilesynchronizerthread.CloudFileSynchronizerThread):
    INSTANCE = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.started = False

        __class__.INSTANCE = self

    def start(self):
        assert not self.started
        self.started = True

    def run(self):
        pass


fake_gdrive_client = None

class FakeGoogleDriveClient:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fake_is_connected = False
        self.local_token_connection_succeeds = True
        self.connect_with_browser_succeeds = True
        self.files = [
            {'name': 'some_file', 'id': 'some-id'},
            {'name': 'test-bookmarks.yaml', 'id': 'bookmarks-file-id'}
        ]
        self.bookmarks = {}

        global fake_gdrive_client
        fake_gdrive_client = self

    def is_connected(self):
        return self.fake_is_connected

    def connect_with_local_token(self):
        if self.local_token_connection_succeeds:
            self.fake_is_connected = True
        else:
            raise gdrive_client.LocalTokenInvalid__ShouldTryRefreshWithBrowserException()

    def connect_with_browser(self):
        if self.connect_with_browser_succeeds:
            self.fake_is_connected = True
        else:
            raise Exception('could not connect')

    def list_files(self):
        if not self.fake_is_connected:
            raise Exception('not connected')
        return self.files

    def read_file(self, file_id):
        if not self.fake_is_connected:
            raise Exception('Not connected')
        if 'bookmarks-file-id' in self.files:
            assert file_id == 'bookmarks-file-id', 'BookmarkStore unit test should only read bookmarks file'
            return yaml.dump(self.bookmarks)
        raise Exception('File does not exist')


class Test(unittest.TestCase):
    LOCAL_CACHE_FILENAME = '/tmp/test-bookmarks.yaml'
    EXAMPLE_BOOKMARKS = [{'children': [
            {'url': 'https://example.com', 'name': 'example', 'guid': 'some-id', 'children': []},
            {'url': 'https://example.com', 'name': 'another-example', 'guid': 'another-id', 'children': []},
        ]}]

    @mock.patch('utils.drive.cloudfilesynchronizerthread.CloudFileSynchronizerThread')
    @mock.patch('utils.drive.gdrive_client.GoogleDriveClient')
    def setUp(self, gdrive_client_mock, sync_thread_class):
        gdrive_client_mock.side_effect = FakeGoogleDriveClient

        # Mock background sync thread's scheduling
        sync_thread_class.side_effect = FakeCloudFileSyncThread

        # Fake implementation for the cloud file syncer thread
        #self.syncer = FakeSyncer.instance

        # This is the actual result of the unit under test - the ordered list of callbacks and args
        self._response_callback_calls = []

        # Set example bookmarks in drive
        bookmark_store.BookmarkStore.BOOKMARKS_YAML_FILENAME = self.LOCAL_CACHE_FILENAME
        with open(self.LOCAL_CACHE_FILENAME, 'w') as local_cache_file:
            yaml.dump(self.EXAMPLE_BOOKMARKS, local_cache_file)

        # Create unit under test
        self.tested = bookmark_store.BookmarkStore(
            list_bookmarks_callback=self._list_bookmarks_callback,
            connected_to_cloud_callback=self._connected_callback,
            disconnected_from_cloud_callback=self._disconnected_callback,
            browser_authentication_needed_callback=self._browser_auth_required_callback)

        self.sync_thread = FakeCloudFileSyncThread.INSTANCE
        self.gdrive_client = fake_gdrive_client
        assert self.gdrive_client is not None

        # Set example bookmarks in local cache
        self.gdrive_client.bookmarks = self.EXAMPLE_BOOKMARKS

    def notest_connected_callback_invoked_on_connection_established(self):
        # Run
        self._artificially_run_syncer_thread()

        # Validate that the only callback was the connection success callback
        self.assertEquals(self._response_callback_calls, [('connected', (), {})])

    def notest_async_connect_asks_browser_auth_when_local_token_connection_fails(self):
        # Setup
        self.gdrive_client.local_token_connection_succeeds = False

        # Run
        self._artificially_run_syncer_thread(action_on_wait_for_user_request_for_browser_auth='stop')

        # Validate that the only callback was the connection success callback
        self.assertEquals(self._response_callback_calls, [('browser_auth_required', (), {})])

    def notest_async_browser_connect_invokes_connected_callback_on_connection_established(self):
        # Setup
        self.gdrive_client.local_token_connection_succeeds = False

        # Run
        self._artificially_run_syncer_thread()

        # Validate that the only callback was the connection success callback
        self.assertEquals(self._response_callback_calls,
            [
                ('browser_auth_required', (), {}),  # First, connection with local token fails
                ('connected', (), {})  # After user invoked browser connection, the callback is called
            ])

    def test_async_list_bookmarks__returns_bookmarks_when_connected_and_synced(self):
        # Run
        self.tested.async_list_bookmarks()
        self._artificially_run_syncer_thread()

        # Validate
        self.assertEquals(self._response_callback_calls[0], ('connected', (), {}))
        self.assertEquals(self._response_callback_calls[1],
            ('list_bookmarks',
             (self.EXAMPLE_BOOKMARKS[0]['children'],),
             {'sync_status': 'connecting_local-cache-only'})
            )
        self.assertEquals(len(self._response_callback_calls), 2)

    def notest_async_list_bookmarks__returns_bookmarks_and_creates_cache_from_drive_file_when_missing(self):
        # Setup (remove cache)
        os.unlink(self.LOCAL_CACHE_FILENAME)

        # Run
        self.tested.async_list_bookmarks()

        # Schedule thread
        self._artificially_run_syncer_thread()

        # Validate
        self.assertEquals(self._response_callback_calls[0], ('connected', (), {}))
        # Validate bookmarks
        self.assertEquals(self._response_callback_calls[1],
            ('list_bookmarks',
             (self.EXAMPLE_BOOKMARKS[0]['children'],),
             {'is_connected': True})
            )
        self.assertEquals(len(self._response_callback_calls), 2)
        # Validate cache creation
        with open(self.LOCAL_CACHE_FILENAME) as cache_file:
            cache = yaml.safe_load(cache_file)
        self.assertEquals(cache, self.EXAMPLE_BOOKMARKS)

    def notest_async_list_bookmarks__returns_bookmarks_and_creates_drive_file_from_cache_when_missing(self):
        # Run
        self.tested.async_list_bookmarks()

        # Schedule thread
        self._artificially_run_syncer_thread()

        # Validate
        self.assertEquals(self._response_callback_calls[0], ('connected', (), {}))
        # Validate bookmarks
        self.assertEquals(self._response_callback_calls[1],
            ('list_bookmarks',
             (self.EXAMPLE_BOOKMARKS[0]['children'],),
             {'is_connected': True})
            )
        self.assertEquals(len(self._response_callback_calls), 2)
        # Validate cache creation
        with open(self.LOCAL_CACHE_FILENAME) as cache_file:
            cache = yaml.safe_load(cache_file)
        self.assertEquals(cache, self.EXAMPLE_BOOKMARKS)

    def _list_bookmarks_callback(self, *args, **kwargs):
        self._response_callback_calls.append(('list_bookmarks', args, kwargs))

    def _connected_callback(self, *args, **kwargs):
        self._response_callback_calls.append(('connected', args, kwargs))

    def _disconnected_callback(self, *args, **kwargs):
        self._response_callback_calls.append(('disconnected', args, kwargs))

    def _browser_auth_required_callback(self, *args, **kwargs):
        self._response_callback_calls.append(('browser_auth_required', args, kwargs))

    def _artificially_run_syncer_thread(self,
            action_on_wait_for_user_request_for_browser_auth='continue',
            ):
        assert self.sync_thread.started, ('Fake scheduling should not be done as part of the test at this '
            'point, as the thread start method was not called by the tested unit')

        # TODO find a better way to schedule the background thread during testing!!!
        # The following is bad code (since it's whitebox/implementation dependent), and should be fixed.
        # But for initial revision for this testing, it's good enough.
        with mock.patch.object(self.sync_thread, '_user_invoked_browser_authentication') as browser_auth_requested:
            if action_on_wait_for_user_request_for_browser_auth == 'stop':
                browser_auth_requested.wait.side_effect = StopIteration

            for _ in range(10):
                if self.sync_thread._incoming_requests.empty():
                    self.sync_thread._incoming_requests.put({'type': '___nothing___'})
                try:
                    self.tested._cloud_bookmarks_syncer.run_once()
                except StopIteration:
                    break


if __name__ == "__main__":
    unittest.main()
