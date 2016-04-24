"""
Access the Google Calendar API and retrieve events from a calendar over a
specified time range.
"""

__author__ = 'ajay@roopakalu.com (Ajay Roopakalu)'

from oauth2client import client
from googleapiclient import sample_tools

import log

logging = log.Log(__name__)


class Calendar(object):
  """Class to access the Google Calendar API."""

  def __init__(self, argv):
    """Init.

    Args:
      argv: ([str]) List of command-line arguments passed to main program.
    """
    self._service, _ = sample_tools.init(
        argv, 'calendar', 'v3', __doc__, __file__,
        scope='https://www.googleapis.com/auth/calendar.readonly')

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
    try:
      events = self._service.events().list(
          calendarId=calendar_id, orderBy='startTime',
          singleEvents=True, timeMin=start.isoformat(),
          timeMax=end.isoformat()).execute()
      return events.get('items')
    except client.AccessTokenRefreshError:
      logging.exception(
          'The credentials have been revoked or expired, please re-run the '
          'application to re-authorize.')
      sys.exit(-1)
