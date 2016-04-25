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
import prometheus_client as pc
import requests
import nmap

from datetime import datetime
from datetime import timedelta
from dateutil import tz

import calendar_client
import log
import keys

registry = pc.CollectorRegistry()
location_metric = pc.Gauge(
    'location', 'Location of user', ['home', 'away'], registry=registry)
ambient_temperature_metric = pc.Gauge(
    'ambient_temperature', 'Current ambient temperature in Fahrenheit',
    registry=registry)
target_temperature_high_metric = pc.Gauge(
    'target_temperature_high', 'Target high temperature in Fahrenheit',
    registry=registry)
target_temperature_low_metric = pc.Gauge(
    'target_temperature_low', 'Target low temperature in Fahrenheit',
    registry=registry)
humidity_metric = pc.Gauge(
    'humidity', 'Humidity in percentage', registry=registry)
hvac_state_metric = pc.Gauge(
    'hvac_state', 'State of HVAC ("heating", "cooling", or "off")',
    ['state'], registry=registry)
fan_active_metric = pc.Gauge(
    'fan_timer_active', 'State of fan ("on" or "off")', ['state'],
    registry=registry)

logging = log.Log(__name__)

EPOCH = datetime(1970, 1, 1)
VALID_HVAC_STATES = frozenset(['heating', 'cooling', 'off'])

STRUCTURE_URL = 'https://developer-api.nest.com/structures/'
THERMOSTATS_URL = 'https://developer-api.nest.com/devices/thermostats/'

STATUS_HOME = '"home"'
STATUS_AWAY = '"away"'

ENTER_WORK_REGEX = re.compile('I entered work')
EXIT_WORK_REGEX = re.compile('I exited work')
WFH_REGEX = re.compile('WFH')
MIDDAY = 12 # Hour of the day to indicate noon


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
      logging.info('Setting status of %s to : %s',structure_id, status)
      response = requests.put(
          STRUCTURE_URL + structure_id + '/away',
          params=params, headers=headers, data=status)
      results[structure_id] = (response.text == status)
    else:
      logging.info(
          'Target status of %s for %s already set.', status, structure_id)
  if status == STATUS_HOME:
    location_metric.labels('home').set(1)
  elif status == STATUS_AWAY:
    location_metric.labels('away').set(1)
  return results


def RecordStats(thermostat_model):
  for thermostat in thermostat_model.itervalues():
    ambient_temperature_metric.set(thermostat['ambient_temperature_f'])
    target_temperature_high_metric.set(thermostat['target_temperature_high_f'])
    target_temperature_low_metric.set(thermostat['target_temperature_low_f'])
    humidity_metric.set(thermostat['humidity'])

    fan_active_metric.labels('on').set(int(thermostat['fan_timer_active']))
    fan_active_metric.labels('off').set(int(not thermostat['fan_timer_active']))

    hvac_state = thermostat['hvac_state']
    if hvac_state not in VALID_HVAC_STATES:
      logging.warning('Unexpected HVAC state: %s', hvac_state)
    else:
      for state in VALID_HVAC_STATES:
        hvac_state_metric.labels(state).set(int(state == hvac_state))


def PushMetrics():
  if keys.PROMETHEUS_ENDPOINT is not None:
    logging.info('Pushing metrics to %s', keys.PROMETHEUS_ENDPOINT)
    ret = pc.push_to_gateway(
        keys.PROMETHEUS_ENDPOINT, job='nest-wfh', registry=registry)

def main(argv):
  now = datetime.now(tz=tz.tzlocal())
  localized_now = now.astimezone(tz.gettz(keys.WORK_HOURS_CALENDAR_TZ))
  today = localized_now.replace(hour=0, minute=0, second=0, microsecond=0)
  tomorrow = today + timedelta(days=1)

  logging.info('Retrieving known thermostats.')
  thermostat_model = GetAllThermostats(keys.ACCESS_TOKEN)
  RecordStats(thermostat_model)
  PushMetrics()

  logging.info('Retrieving relevant calendar events.')
  calendar_instance = calendar_client.Calendar(argv)
  events = calendar_instance.GetEvents(
      keys.WORK_HOURS_CALENDAR_ID, today, tomorrow)
  if not events:
    logging.info('No events found.')
    exit(0)

  structure_ids = GetStructureIds(thermostat_model)

  for event in events:
    try:
      # If WFH, always set status to HOME.
      if WFH_REGEX.match(event.get('summary')):
        logging.info(
            SetAwayStatus(keys.ACCESS_TOKEN, structure_ids, status=STATUS_HOME))

      startEntity = event.get('start')
      # Ignore full-day events here.
      if not startEntity.get('dateTime'):
        continue
      startTime = dateutil.parser.parse(startEntity.get('dateTime'))

      if today < startTime < tomorrow:
          if (localized_now.hour <= MIDDAY and
              ENTER_WORK_REGEX.match(event.get('summary'))):
            logging.info('User is at work..')
            logging.info(
                SetAwayStatus(
                    keys.ACCESS_TOKEN, structure_ids, status=STATUS_AWAY))
          if (localized_now.hour > MIDDAY and
              EXIT_WORK_REGEX.match(event.get('summary'))):
            logging.info('User is coming home..')
            logging.info(
                SetAwayStatus(
                    keys.ACCESS_TOKEN, structure_ids, status=STATUS_HOME))
    except Exception as e:
      logging.exception('Error while performing operation: %s', e)

  PushMetrics()

if __name__ == '__main__':
  main(sys.argv)
