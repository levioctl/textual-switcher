from __future__ import print_function
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from apiclient.http import MediaFileUpload


class GoogleDriveClient(object):
    # If modifying these scopes, delete the file token.pickle.
    SCOPES = ['https://www.googleapis.com/auth/drive.appdata']

    def __init__(self, explicit_authentication_succeeded):
        self._service = None
        self._explicit_authentication_succeeded = explicit_authentication_succeeded
        self._try_to_authenticate_with_local_credentials()

    def try_to_authenticate_explicitly(self):
        # This fetches credentials to reside locally
        print('aaaaaaaaaaa')
        flow = InstalledAppFlow.from_client_secrets_file(
            os.path.expanduser('~/.config/textual-switcher/credentials.json'), self.SCOPES)
        print('bbbbbbbbbbb')
        creds = flow.run_local_server(port=0)
        print('ccccccccccc')
        self._write_token(creds)

        # This tries to authenticate using these credentials
        self._try_to_authenticate_with_local_credentials()

        # Tell the user that connection is established
        self._explicit_authentication_succeeded()

    def is_authenticated(self):
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
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    def _try_to_authenticate_with_local_credentials(self):
        creds = None
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # Wait for user to actively authenticate with web browser
                return
            # Save the credentials for the next run
            self._write_token(creds)

        self._service = build('drive', 'v3', credentials=creds)


class GoogleDriveFileSynchronizer(object):
    def __init__(self, filename, external_conected_callback, create_if_does_not_exist=False):
        self._external_connected_callback = external_conected_callback
        self._client = GoogleDriveClient(self._explicit_authentication_succeeded)
        self._filename = filename

        # Read file ID if client managed to authenticate (synchronously). If not, explicit authentication
        # is required.
        if self._client.is_authenticated():
            self._read_file_id()

    def _read_file_id(self):
        # Search for file ID
        self._file_id = self._get_file_id()
        # Create file if does not exist, and store its file ID
        file_exists = self._file_id is not None
        if not file_exists and create_if_does_not_exist:
            self._file_id = self._client.create_file(self._filename)['id']

    def _explicit_authentication_succeeded(self):
        self._read_file_id()

        # Tell the user that connected is established
        self._external_connected_callback()

    def try_to_authenticate_explicitly(self):
        return self._client.try_to_authenticate_explicitly()

    def is_authenticated(self):
        return self._client.is_authenticated()

    def _get_file_id(self):
        file_id = None
        for _file in self._client.list_files():
            # Process change
            print('Found file in drive: %s (%s)' % (_file.get('name'), _file.get('id')))
            if _file.get('name') == os.path.basename(self._filename):
                file_id = _file['id']
        return file_id

    def read_remote_file(self):
        print("Sending a request to drive to read file {}".format(self._file_id))
        contents = self._client.read_file(self._file_id)
        return contents

    def write_to_remote_file(self):
        print("Writing to file ID {} from file {}".format(self._file_id, self._filename))

        result = self._client.update_file(self._file_id, self._filename)


def main():
    bookmarks_file_syncer = GoogleDriveFileSynchronizer('bookmarks.yaml',
                                                        create_if_does_not_exist=True)
    bookmarks_file_syncer.write_to_remote_file()
    contents = bookmarks_file_syncer.read_remote_file()
    print(contents)


if __name__ == "__main__":
    main()
