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
from dateutil.tz import tzlocal

from oauth2client import client
from googleapiclient import sample_tools

import keys

STRUCTURE_URL = 'https://developer-api.nest.com/structures/'
THERMOSTATS_URL = 'https://developer-api.nest.com/devices/thermostats/'

STATUS_HOME = '"home"'
STATUS_AWAY = '"away"'

ENTER_WORK_REGEX = re.compile('I entered work')
EXIT_WORK_REGEX = re.compile('I exited work')


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


def SetAwayStatus(access_token, structure_ids, status):
  params = {'auth': access_token}
  headers = {'Content-Type': 'application/json'}
  results = {}
  for structure_id in structure_ids:
    response = requests.put(
        STRUCTURE_URL + structure_id + '/away',
        params=params, headers=headers, data=status)
    results[structure_id] = (response.text == status)
  return results


def GetWorkStatusEvents(service):
  try:
    events = service.events().list(
        calendarId=keys.WORK_HOURS_CALENDAR_ID, orderBy='startTime',
        singleEvents=True).execute()
    return events.get('items')
  except client.AccessTokenRefreshError:
    print ('The credentials have been revoked or expired, please re-run'
      'the application to re-authorize.')
    sys.exit(-1)

def main(argv):
  now = datetime.now()
  today = datetime(now.year, now.month, now.day, tzinfo=tzlocal())
  tomorrow = today + timedelta(days=1)

  thermostat_model = GetAllThermostats(keys.ACCESS_TOKEN)
  structure_ids = GetStructureIds(thermostat_model)

  service, flags = sample_tools.init(
      argv, 'calendar', 'v3', __doc__, __file__,
      scope='https://www.googleapis.com/auth/calendar.readonly')

  for event in GetWorkStatusEvents(service):
    startTime = dateutil.parser.parse(event.get('start').get('dateTime'))
    if today < startTime and startTime < tomorrow:
      if EXIT_WORK_REGEX.match(event.get('summary')):
        print 'User is coming home..'
        print SetAwayStatus(
            keys.ACCESS_TOKEN, structure_ids, status=STATUS_HOME)
      elif ENTER_WORK_REGEX.match(event.get('summary')):
        print 'User is at work..'
        print SetAwayStatus(
            keys.ACCESS_TOKEN, structure_ids, status=STATUS_AWAY)


if __name__ == '__main__':
  main(sys.argv)
