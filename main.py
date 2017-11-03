"""
Nest-WFH is a project that aims to prevent your Nest thermostat from going into
auto-away mode if you are home.

The program works by querying your calendar to look for specific events. If so,
it will manually set all thermostats to "home". This is meant to be run as a
cron job.
"""
__author__ = 'ajay@roopakalu.com (Ajay Roopakalu)'

import re
import sys

import dateutil.parser
import prometheus_client as pc

from absl import flags
from datetime import datetime
from datetime import timedelta
from dateutil import tz

import calendar_client
import log
import nest
import keys
import weather

flags.DEFINE_boolean('set_status', True, 'Whether to modify Nest state.')

FLAGS = flags.FLAGS

registry = pc.CollectorRegistry()
ambient_temperature_metric = pc.Gauge(
    'ambient_temperature', 'Current ambient temperature in Fahrenheit',
    registry=registry)
target_temperature_high_metric = pc.Gauge(
    'target_temperature_high', 'Target high temperature in Fahrenheit',
    registry=registry)
target_temperature_low_metric = pc.Gauge(
    'target_temperature_low', 'Target low temperature in Fahrenheit',
    registry=registry)
external_temperature_metric = pc.Gauge(
    'external_temperature', 'Current external temperature in Fahrenheit',
    registry=registry)
humidity_metric = pc.Gauge(
    'humidity', 'Internal humidity in percentage', registry=registry)
external_humidity_metric = pc.Gauge(
  'external_humidity', 'External humidity in percentage', registry=registry)
hvac_state_metric = pc.Gauge(
    'hvac_state', 'State of HVAC ("heating", "cooling", or "off")',
    ['state'], registry=registry)
fan_active_metric = pc.Gauge(
    'fan_timer_active', 'State of fan ("on" or "off")', ['state'],
    registry=registry)
user_state_metric = pc.Gauge(
    'user_state', 'State of user ("home", "away", or "auto-away")',
    ['structure_id', 'state'], registry=registry)

logging = log.Log(__name__)

EPOCH = datetime(1970, 1, 1)
VALID_HVAC_STATES = frozenset(['heating', 'cooling', 'off'])
VALID_AWAY_STATES = frozenset(['home', 'away', 'auto-away'])

DEVICES_URL = 'https://developer-api.nest.com/devices/'
STRUCTURE_URL = 'https://developer-api.nest.com/structures/'
THERMOSTATS_URL = 'https://developer-api.nest.com/devices/thermostats/'

STATUS_HOME = '"home"'
STATUS_AWAY = '"away"'

ENTER_WORK_REGEX = re.compile('I entered work')
EXIT_WORK_REGEX = re.compile('I exited work')
WFH_REGEX = re.compile('WFH')
MIDDAY = 12 # Hour of the day to indicate noon


def RecordStats(thermostats, structures, external_weather):
  for thermostat in thermostats.itervalues():
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

  for structure_id in structures:
    user_state = structures[structure_id]['away']
    if user_state not in VALID_AWAY_STATES:
      logging.warning('Unexpected away state: %s', user_state)
    else:
      for state in VALID_AWAY_STATES:
        user_state_metric.labels(
            structure_id, state).set(int(state == user_state))

  external_temperature_metric.set(external_weather['temp'])
  external_humidity_metric.set(external_weather['humidity'])


def PushMetrics():
  if keys.PROMETHEUS_ENDPOINT is not None:
    logging.info('Pushing metrics to %s', keys.PROMETHEUS_ENDPOINT)
    pc.push_to_gateway(
        keys.PROMETHEUS_ENDPOINT, job='nest-wfh', registry=registry)


def Run():
  now = datetime.now(tz=tz.tzlocal())
  localized_now = now.astimezone(tz.gettz(keys.WORK_HOURS_CALENDAR_TZ))
  today = localized_now.replace(hour=0, minute=0, second=0, microsecond=0)
  tomorrow = today + timedelta(days=1)

  logging.info('Retrieving known thermostats.')
  thermostats = nest.GetAllThermostats(keys.NEST_ACCESS_TOKEN, THERMOSTATS_URL)
  structure_ids = nest.GetStructureIds(thermostats)
  logging.info('Retrieving known structures.')
  structures = nest.GetStructures(
      keys.NEST_ACCESS_TOKEN, STRUCTURE_URL, structure_ids)
  logging.info('Retrieving external temperature.')
  external_weather = weather.GetCurrentExternalWeather(
      keys.OWM_API_KEY, keys.LOCATION_CITY_ID)
  RecordStats(thermostats, structures, external_weather)
  PushMetrics()

  logging.info('Retrieving relevant calendar events.')
  calendar_instance = calendar_client.Calendar()
  events = calendar_instance.GetEvents(
      keys.WORK_HOURS_CALENDAR_ID, today, tomorrow)
  if not events:
    logging.info('No events found.')
    exit(0)

  for event in events:
    try:
      # If WFH, always set status to HOME.
      if WFH_REGEX.match(event.get('summary')):
        logging.info(
            nest.SetAwayStatus(
                keys.NEST_ACCESS_TOKEN, STRUCTURE_URL, structure_ids,
                status=STATUS_HOME))

      startEntity = event.get('start')
      # Ignore full-day events here.
      if not startEntity.get('dateTime'):
        continue
      startTime = dateutil.parser.parse(startEntity.get('dateTime'))

      if today < startTime < tomorrow:
        if (localized_now.hour <= MIDDAY and
              ENTER_WORK_REGEX.match(event.get('summary'))):
          logging.info('User is at work..')
          if FLAGS.set_status:
            logging.info(
              nest.SetAwayStatus(
                keys.NEST_ACCESS_TOKEN, STRUCTURE_URL, structure_ids,
                status=STATUS_AWAY))
        if (localized_now.hour > MIDDAY and
              EXIT_WORK_REGEX.match(event.get('summary'))):
          logging.info('User is coming home..')
          if FLAGS.set_status:
            logging.info(
              nest.SetAwayStatus(
                keys.NEST_ACCESS_TOKEN, STRUCTURE_URL, structure_ids,
                status=STATUS_HOME))
    except Exception as e:
      logging.exception('Error while performing operation: %s', e)

  PushMetrics()


def main(argv):
  FLAGS(argv)
  Run()

if __name__ == '__main__':
  main(sys.argv)
