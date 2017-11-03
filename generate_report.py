"""
Standalone tool to generate report about number of hours worked.

Example:
  To get a report for the last four weeks:
    $ python generate_report.py --start_weeks=4
"""

__author__ = 'ajay@roopakalu.com (Ajay Roopakalu)'

import re
import sys

import dateutil.parser

from absl import flags
from datetime import datetime
from datetime import timedelta
from dateutil import tz

import calendar_client
import keys


flags.DEFINE_integer('start_weeks', 12, 'Weeks ago to start report.')

flags.DEFINE_integer('end_weeks', 0, 'Weeks ago to end report.')

flags.DEFINE_string(
    'mode', 'human', 'Format of outputted report. Must be one of: "human",'
    '"gnuplot", "csv", or "sheets" (Google Sheets).')

FLAGS = flags.FLAGS

WFH_REGEX = re.compile(r'WFH')
OOO_REGEX = re.compile(r'OOO')
ENTER_WORK_REGEX = re.compile(r'I entered work')
EXIT_WORK_REGEX = re.compile(r'I exited work')


def GenerateReport():
  """Generate report about hours worked."""
  now = datetime.now(tz=tz.tzlocal())
  localized_now = now.astimezone(tz.gettz(keys.WORK_HOURS_CALENDAR_TZ))
  today = localized_now.replace(hour=0, minute=0, second=0, microsecond=0)
  today -= timedelta(weeks=FLAGS.end_weeks)
  start = today - timedelta(weeks=FLAGS.start_weeks)

  calendar_instance = calendar_client.Calendar()

  # Store report information as a list of dicts with the date, enter work time,
  # and exit work time, and timedelta between them.
  report = []

  for event in calendar_instance.GetEvents(
      keys.WORK_HOURS_CALENDAR_ID, start, today):
    startEntity = event.get('start')
    summary = event.get('summary')

    # Skip OOOs (out of office).
    if OOO_REGEX.match(summary):
      continue
    # Treat WFH as 8 hours worked.
    if WFH_REGEX.match(summary):
      startDate = dateutil.parser.parse(startEntity.get('date'))
      report.append({
          'date': startDate.date(),
          'start': startDate.replace(hour=9),
          'end': startDate.replace(hour=17),
          'delta': timedelta(hours=8)})
    # All other events should not be all-day events.
    if not startEntity.get('dateTime'):
      continue

    startTime = dateutil.parser.parse(startEntity.get('dateTime'))
    startDate = startTime.date()

    if report and report[-1]['date'] == startDate:
      report_entity = report[-1]
      report_entity['end'] = startTime
      report_entity['delta'] = (
          report_entity['end'] - report_entity['start'])
    else:
      report.append({'date': startDate, 'start': startTime})

  PrintReport(report)


def PrintReport(report):
  for index, line in enumerate(report):
    # Skip incomplete lines.
    if 'delta' not in line.keys() or 'date' not in line.keys():
      continue
    if FLAGS.mode == 'human':
      # Print date as YYYY-MM-DD and delta as HH:MM:SS.
      print '%s %s' % (line['date'], line['delta'])
    elif FLAGS.mode == 'gnuplot':
      # Print just the index and the number of hours as a float
      print '%d %f' % (index, line['delta'].total_seconds() / 60. / 60.)
    elif FLAGS.mode == 'csv':
      print '%s, %s' % (
          line['date'], line['delta'].total_seconds() / 60. / 60.)
    elif FLAGS.mode == 'sheets':
      print '%s\t%s' % (
          line['date'], line['delta'].total_seconds() / 60. / 60.)


def main(argv):
  FLAGS(argv)
  GenerateReport()


if __name__ == '__main__':
  main(sys.argv)
