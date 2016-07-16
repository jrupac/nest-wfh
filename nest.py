"""
Implementation of the Nest API.
"""
__author__ = 'ajay@roopakalu.com (Ajay Roopakalu)'

import requests

import log

logging = log.Log(__name__)


def GetAllThermostats(access_token, thermostats_url):
  response = requests.get(thermostats_url, params={'auth': access_token})
  return response.json()


def GetStructureIds(thermostats):
  structure_ids = []
  for thermostat in thermostats.itervalues():
    structure_ids.append(thermostat['structure_id'])
  return structure_ids


def GetStructures(access_token, structure_url, structure_ids):
  params = {'auth': access_token}
  headers = {'Content-Type': 'application/json'}
  results = {}
  for structure_id in structure_ids:
    response = requests.get(
        structure_url + structure_id, params=params, headers=headers)
    results[structure_id] = response.json()
  return results


def SetAwayStatus(access_token, structure_url, structure_ids, status):
  params = {'auth': access_token}
  headers = {'Content-Type': 'application/json'}
  results = {}
  existing_structures = GetStructures(access_token, structure_ids)

  for structure_id in structure_ids:
    if existing_structures[structure_id]['away'] != status:
      logging.info('Setting status of %s to : %s', structure_id, status)
      response = requests.put(
          structure_url + structure_id + '/away',
          params=params, headers=headers, data=status)
      results[structure_id] = (response.text == status)
    else:
      logging.info(
          'Target status of %s for %s already set.', status, structure_id)
  return results