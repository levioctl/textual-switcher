from __future__ import print_function
import json
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from apiclient.http import MediaFileUpload


class LocalTokenInvalid__ShouldTryRefreshWithBrowserException(Exception): pass


class GoogleDriveClient(object):
    # If modifying these scopes, delete the file token.json.
    SCOPES = ['https://www.googleapis.com/auth/drive.appdata']
    #SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly']
    creds_path = os.path.expanduser('~/.config/textual-switcher/credentials.json')

    def __init__(self):
        self._creds = None
        self._service = None

    def connect_with_local_token(self):
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        assert self._service is None, 'Tried to connect but already connected'
        if os.path.exists('token.json'):
            self._creds = Credentials.from_authorized_user_file('token.json', self.SCOPES)
            if self._creds.valid:
                self._service = build('drive', 'v3', credentials=self._creds)
                print('Connected with local token.')

        if self._service is None:
            raise LocalTokenInvalid__ShouldTryRefreshWithBrowserException()

    def connect_with_browser(self):
        # If there are no (valid) credentials available, let the user log in.
        if self._creds and self._creds.expired and self._creds.refresh_token:
            self._creds.refresh(Request())
        else:
            # Wait for user to actively authenticate with web browser
            flow = InstalledAppFlow.from_client_secrets_file(
                self.creds_path, self.SCOPES)
            self._creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        self._write_token(self._creds)

        self._service = build('drive', 'v3', credentials=self._creds)

    def is_connected(self):
        return self._service is not None

    def create_file(self, filename):
        file_metadata = {
            'name': filename,
            'parents': ['appDataFolder']
        }
        media = MediaFileUpload(filename,
                                mimetype='application/text')
        _file = self._service.files().create(body=file_metadata,
                                      media_body=media,
                                      fields='id').execute()
        return _file

    def read_file(self, file_id):
        return self._service.files().get_media(fileId=file_id).execute()

    def update_file(self, file_id, filename):
        file_metadata = {
            'fileId': file_id
        }
        media = MediaFileUpload(filename,
                                mimetype='application/text')
        _file = self._service.files().update(
                                      fileId=file_id,
                                      body=file_metadata,
                                      media_body=media).execute()
        return _file

    def list_files(self):
        response = self._service.files().list(spaces='appDataFolder',
                                          fields='nextPageToken, files(id, name)',
                                          pageSize=10).execute()
        return response['files']

    def _write_token(self, creds):
        with open('token.json', 'w') as token:
            token.write(creds.to_json())


class GoogleDriveFileSynchronizer(object):
    def __init__(self, filename, client):
        self._client = client
        self._filename = filename
        self._file_id = None

    def does_remote_file_exist(self):
        if self._file_id is None:
            self._read_file_id()
        return self._file_id is not None

    def create_file(self):
        self._file_id = self._client.create_file(self._filename)['id']
        assert self._file_id is not None
        print('File created. ID: {}'.format(self._file_id))

    def read_remote_file(self):
        if self._file_id is None:
            self._read_file_id()
        print("Sending a request to drive to read file {}".format(self._file_id))
        contents = self._client.read_file(self._file_id)
        return contents

    def write_to_remote_file(self):
        if self._file_id is None:
            self._read_file_id()

        print("Writing to file ID {} from file {}".format(self._file_id, self._filename))

        result = self._client.update_file(self._file_id, self._filename)

    def _read_file_id(self):
        # Search for file ID
        self._file_id = self._get_file_id()

    def _get_file_id(self):
        file_id = None
        for _file in self._client.list_files():
            # Process change
            print('Found file in drive: %s (%s)' % (_file.get('name'), _file.get('id')))
            if _file.get('name') == os.path.basename(self._filename):
                file_id = _file['id']
        return file_id


if __name__ == "__main__":
    client = GoogleDriveClient()


    try:
        print('Trying to connect with local token...')
        client.connect_with_local_token()
    except:
        print('Trying to connect with browser...')
        client.connect_with_browser()

    bookmarks_file_syncer = GoogleDriveFileSynchronizer('/tmp/bookmarks.yaml',
                                                        client=client
                                                        )

    print('Connected. writing to file...')
    with open('/tmp/bookmarks.yaml', 'w') as f:
        initial = [{'guid': 'ROOT', 'children': []}]
        import yaml
        yaml.dump(initial, f)
    if not bookmarks_file_syncer.does_remote_file_exist():
        bookmarks_file_syncer.create_file()
    else:
        bookmarks_file_syncer.write_to_remote_file()
    contents = bookmarks_file_syncer.read_remote_file()
    print(contents)
    bookmarks_file_syncer._client._service.files().delete(fileId=bookmarks_file_syncer._file_id)
