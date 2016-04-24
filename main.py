"""
Nest-WFH is a project that aims to prevent your Nest thermostat from going into
auto-away mode if your phone is also at home.

The program works by querying to see if your phone's MAC address appears on the
network. If so, it will manually set all thermostats to "home". This is meant
to be run as a cron job.
"""

__author__ = 'ajay@roopakalu.com (Ajay Roopakalu)'

import logging
import logging.handlers
import re
import subprocess
import sys

import dateutil.parser
import requests
import nmap

from datetime import datetime
from datetime import timedelta
from dateutil import tz

import calendar_client
import keys

LOG_FILENAME = '/var/log/nest-wfh/nest-wfh.INFO'

STRUCTURE_URL = 'https://developer-api.nest.com/structures/'
THERMOSTATS_URL = 'https://developer-api.nest.com/devices/thermostats/'

STATUS_HOME = '"home"'
STATUS_AWAY = '"away"'

ENTER_WORK_REGEX = re.compile('I entered work')
EXIT_WORK_REGEX = re.compile('I exited work')
WFH_REGEX = re.compile('WFH')
MIDDAY = 12 # Hour of the day to indicate noon

LOGGER = None


def Init():
  global LOGGER
  fmt = '%(asctime)-15s %(threadName)s %(filename)s:%(lineno)d %(message)s'
  LOGGER = logging.getLogger(__name__)
  LOGGER.setLevel(logging.INFO)
  # Rotate at 1M bytes, store 5 old versions
  handler = logging.handlers.RotatingFileHandler(
      LOG_FILENAME, maxBytes=1>>20, backupCount=5)
  handler.setFormatter(logging.Formatter(fmt))
  LOGGER.addHandler(handler)


def IsReferenceDeviceOnNetwork(ip_subnet, mac_address):
  # Refresh the ARP cache by doing a fast scan of hosts on this subnet
  nm = nmap.PortScanner()
  nm.scan(hosts=ip_subnet, arguments='-sP')
  # Query the ARP cache for the specified MAC address
  proc = subprocess.Popen(['arp', '-n'], stdout=subprocess.PIPE)
  output, _ = proc.communicate()
  for line in output.split('\n'):
    if line.find(mac_address) > 0:
      return True
  return False


def GetAllThermostats(access_token):
  response = requests.get(THERMOSTATS_URL, params={'auth': access_token})
  return response.json()


def GetStructureIds(thermostat_model):
  structure_ids = []
  for thermostat in thermostat_model.itervalues():
    structure_ids.append(thermostat['structure_id'])
  return structure_ids


def GetAwayStatus(access_token, structure_ids):
  params = {'auth': access_token}
  headers = {'Content-Type': 'application/json'}
  results = {}
  for structure_id in structure_ids:
    response = requests.get(
        STRUCTURE_URL + structure_id + '/away',
        params=params, headers=headers)
    results[structure_id] = response.text
  return results


def SetAwayStatus(access_token, structure_ids, status):
  params = {'auth': access_token}
  headers = {'Content-Type': 'application/json'}
  results = {}
  existing_statuses = GetAwayStatus(access_token, structure_ids)

  for structure_id in structure_ids:
    if existing_statuses[structure_id] != status:
      LOGGER.info('Setting status of %s to : %s',structure_id, status)
      response = requests.put(
          STRUCTURE_URL + structure_id + '/away',
          params=params, headers=headers, data=status)
      results[structure_id] = (response.text == status)
    else:
      LOGGER.info(
          'Target status of %s for %s already set.', status, structure_id)
  return results


def GetWorkStatusEvents(service, today, tomorrow):
  try:
    events = service.events().list(
        calendarId=keys.WORK_HOURS_CALENDAR_ID, orderBy='startTime',
        singleEvents=True, timeMin=today.isoformat(),
        timeMax=tomorrow.isoformat()).execute()
    return events.get('items')
  except client.AccessTokenRefreshError:
    LOGGER.warning(
        'The credentials have been revoked or expired, please re-run the '
        'application to re-authorize.')
    sys.exit(-1)

def main(argv):
  Init()

  now = datetime.now(tz=tz.tzlocal())
  localized_now = now.astimezone(tz.gettz(keys.WORK_HOURS_CALENDAR_TZ))
  today = localized_now.replace(hour=0, minute=0, second=0, microsecond=0)
  tomorrow = today + timedelta(days=1)

  LOGGER.info('Retrieving relevant calendar events.')
  calendar_instance = calendar_client.Calendar(argv)
  events = calendar_instance.GetEvents(
      keys.WORK_HOURS_CALENDAR_ID, today, tomorrow)
  if not events:
    LOGGER.info('No events found.')
    exit(0)

  LOGGER.info('Retrieving known thermostats.')
  thermostat_model = GetAllThermostats(keys.ACCESS_TOKEN)
  structure_ids = GetStructureIds(thermostat_model)

  for event in events:
    try:
      # If WFH, always set status to HOME.
      if WFH_REGEX.match(event.get('summary')):
        LOGGER.info(
            SetAwayStatus(keys.ACCESS_TOKEN, structure_ids, status=STATUS_HOME))

      startEntity = event.get('start')
      # Ignore full-day events here.
      if not startEntity.get('dateTime'):
        continue
      startTime = dateutil.parser.parse(startEntity.get('dateTime'))

      if today < startTime < tomorrow:
          if (localized_now.hour <= MIDDAY and
              ENTER_WORK_REGEX.match(event.get('summary'))):
            LOGGER.info('User is at work..')
            LOGGER.info(
                SetAwayStatus(
                    keys.ACCESS_TOKEN, structure_ids, status=STATUS_AWAY))
          if (localized_now.hour > MIDDAY and
              EXIT_WORK_REGEX.match(event.get('summary'))):
            LOGGER.info('User is coming home..')
            LOGGER.info(
                SetAwayStatus(
                    keys.ACCESS_TOKEN, structure_ids, status=STATUS_HOME))
    except Exception as e:
      LOGGER.exception('Error while performing operation: %s', e)


if __name__ == '__main__':
  main(sys.argv)
