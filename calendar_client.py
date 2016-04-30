"""
Access the Google Calendar API and retrieve events from a calendar over a
specified time range.
"""

__author__ = 'ajay@roopakalu.com (Ajay Roopakalu)'

import os
import httplib2

from googleapiclient import discovery
from oauth2client import client
from oauth2client import file as f
from oauth2client import tools

import log

logging = log.Log(__name__)


def InitAuthFlow():
  # N.B.: Most of this code is lifted from googleapiclient.sample_tools.
  name = 'calendar'
  version = 'v3'
  scope = 'https://www.googleapis.com/auth/calendar.readonly'

  client_secrets = os.path.join(
      os.path.dirname(__file__), 'client_secrets.json')

  # Set up a Flow object to be used if we need to authenticate.
  flow = client.flow_from_clientsecrets(
      client_secrets, scope=scope,
      message=tools.message_if_missing(client_secrets),
      redirect_uri='urn:ietf:wg:oauth:2.0:oob')

  # Prepare credentials, and authorize HTTP object with them.
  # If the credentials don't exist or are invalid run through the native
  # client flow. The Storage object will ensure that if successful the good
  # credentials will get written back to a file.
  storage = f.Storage(name + '.dat')
  credentials = storage.get()

  if credentials is None or credentials.invalid:
    auth_uri = flow.step1_get_authorize_url()
    print 'Open the following URI in a browser: %s' % auth_uri
    auth_code = raw_input('Enter the auth code: ')
    credentials = flow.step2_exchange(auth_code)

  storage.put(credentials)
  credentials.set_store(storage)
  http = credentials.authorize(http=httplib2.Http())

  # Construct a service object via the discovery service.
  service = discovery.build(name, version, http=http)
  return service


class Calendar(object):
  """Class to access the Google Calendar API."""

  def __init__(self):
    """Init."""
    self._service = InitAuthFlow()

  def GetEvents(self, calendar_id, start, end):
    """
    Retrieve a list of all events on specified calendar in specified date range.

    Args:
      calendar_id: (str) ID of calendar to query.
      start: Datetime object representing the beginning of the time range.
      end: Datetime object representing the end of the time range.
    Returns:
      List of event objects as dicts or None.
    """
    event_list = []
    page_token = None
    try:
      while True:
        events = self._service.events().list(
            calendarId=calendar_id, orderBy='startTime',
            singleEvents=True, timeMin=start.isoformat(),
            timeMax=end.isoformat(), pageToken=page_token).execute()
        event_list.extend(events['items'])
        page_token = events.get('nextPageToken')
        if not page_token:
          break
    except client.AccessTokenRefreshError:
      logging.exception(
          'The credentials have been revoked or expired, please re-run the '
          'application to re-authorize.')
      exit(-1)
    return event_list
