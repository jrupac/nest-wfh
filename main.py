"""
Nest-WFH is a project that aims to prevent your Nest thermostat from going into
auto-away mode if your phone is also at home.

The program works by querying to see if your phone's MAC address appears on the
network. If so, it will manually set all thermostats to "home". This is meant
to be run as a cron job.
"""

__author__ = 'ajay@roopakalu.com (Ajay Roopakalu)'

import re
import subprocess
import sys

import dateutil.parser
import requests
import nmap

from datetime import datetime
from datetime import timedelta
from dateutil import tz

from oauth2client import client
from googleapiclient import sample_tools

import keys

STRUCTURE_URL = 'https://developer-api.nest.com/structures/'
THERMOSTATS_URL = 'https://developer-api.nest.com/devices/thermostats/'

STATUS_HOME = '"home"'
STATUS_AWAY = '"away"'

ENTER_WORK_REGEX = re.compile('I entered work')
EXIT_WORK_REGEX = re.compile('I exited work')
MIDDAY = 12 # Hour of the day to indicate noon


def IsReferenceDeviceOnNetwork(ip_subnet, mac_address):
  # Refresh the ARP cache by doing a fast scan of hosts on this subnet
  nm = nmap.PortScanner()
  nm.scan(hosts=ip_subnet, arguments='-sP')
  # Query the ARP cache for the specified MAC address
  proc = subprocess.Popen(['arp', '-n'], stdout=subprocess.PIPE)
  output, err = proc.communicate()
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
      print 'Setting status of', structure_id, 'to:', status
      response = requests.put(
          STRUCTURE_URL + structure_id + '/away',
          params=params, headers=headers, data=status)
      results[structure_id] = (response.text == status)
    else:
      print 'Target status of', status, 'for', structure_id, 'already set.'
  return results


def GetWorkStatusEvents(service, today, tomorrow):
  try:
    events = service.events().list(
        calendarId=keys.WORK_HOURS_CALENDAR_ID, orderBy='startTime',
        singleEvents=True, timeMin=today.isoformat(),
        timeMax=tomorrow.isoformat()).execute()
    return events.get('items')
  except client.AccessTokenRefreshError:
    print ('The credentials have been revoked or expired, please re-run'
      'the application to re-authorize.')
    sys.exit(-1)

def main(argv):
  now = datetime.now(tz=tz.tzlocal())
  localized_now = now.astimezone(tz.gettz(keys.WORK_HOURS_CALENDAR_TZ))
  today = localized_now.replace(hour=0, minute=0, second=0, microsecond=0)
  tomorrow = today + timedelta(days=1)

  thermostat_model = GetAllThermostats(keys.ACCESS_TOKEN)
  structure_ids = GetStructureIds(thermostat_model)

  service, flags = sample_tools.init(
      argv, 'calendar', 'v3', __doc__, __file__,
      scope='https://www.googleapis.com/auth/calendar.readonly')

  for event in GetWorkStatusEvents(service, today, tomorrow):
    startTime = dateutil.parser.parse(event.get('start').get('dateTime'))
    if today < startTime and startTime < tomorrow:
      if (localized_now.hour <= MIDDAY and
          ENTER_WORK_REGEX.match(event.get('summary'))):
        print 'User is at work..'
        print SetAwayStatus(
            keys.ACCESS_TOKEN, structure_ids, status=STATUS_AWAY)
      if (localized_now.hour > MIDDAY and
          EXIT_WORK_REGEX.match(event.get('summary'))):
        print 'User is coming home..'
        print SetAwayStatus(
            keys.ACCESS_TOKEN, structure_ids, status=STATUS_HOME)


if __name__ == '__main__':
  main(sys.argv)
