"""
Implementation of the OpenWeatherMap API.
"""
__author__ = 'ajay@roopakalu.com (Ajay Roopakalu)'

OPEN_WEATHER_MAP_URL = 'http://api.openweathermap.org/data/2.5'
WEATHER_URL = '/weather'

import requests

import log

logging = log.Log(__name__)

def GetCurrentExternalTemperature(app_id, city_id):
  params = {
      'APPID': app_id,
      'id': city_id,
      'units': 'imperial'
  }
  response = requests.put(
      OPEN_WEATHER_MAP_URL + WEATHER_URL,
      params=params)
  if response.status_code != 200:
    logging.exception('Unexpected response: ', response.text)
  response_parsed = response.json()
  if 'main' not in response_parsed or 'temp' not in response_parsed['main']:
    logging.exception('Expected fields not in response: ', response.text)
  return response_parsed['main']['temp']
