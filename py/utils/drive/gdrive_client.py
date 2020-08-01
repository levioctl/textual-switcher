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

    def __init__(self):
        self._service = None
        self._authenticate()

    def _authenticate(self):
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
                flow = InstalledAppFlow.from_client_secrets_file(
                    os.path.expanduser('~/.config/textual-switcher/credentials.json'), self.SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

        self._service = build('drive', 'v3', credentials=creds)

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


class GoogleDriveFileSynchronizer(object):
    def __init__(self, filename, create_if_does_not_exist=False):
        self._client = GoogleDriveClient()
        self._filename = filename
        # Search for file ID
        self._file_id = self._get_file_id()
        # Create file if does not exist, and store its file ID
        file_exists = self._file_id is not None
        if not file_exists and create_if_does_not_exist:
            self._file_id = self._client.create_file(self._filename)['id']

    def _get_file_id(self):
        file_id = None
        for _file in self._client.list_files():
            # Process change
            print('Found file: %s (%s)' % (_file.get('name'), _file.get('id')))
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
