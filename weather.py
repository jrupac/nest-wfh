"""
Implementation of the OpenWeatherMap API.
"""
__author__ = 'ajay@roopakalu.com (Ajay Roopakalu)'

OPEN_WEATHER_MAP_URL = 'http://api.openweathermap.org/data/2.5'
WEATHER_URL = '/weather'

import requests

import log

logging = log.Log(__name__)


def GetCurrentExternalWeather(app_id, city_id):
  """Get current weather data at the given city_id.

  Args:
    app_id: (str) OpenWeatherMap API key.
    city_id: (str) OpenWeatherMap City ID.

  Returns:
    Dict containing temperature and humidity data for given location.

  """
  params = {
      'APPID': app_id,
      'id': city_id,
      'units': 'imperial'
  }
  response = requests.get(
      OPEN_WEATHER_MAP_URL + WEATHER_URL,
      params=params)
  if response.status_code != 200:
    logging.exception('Unexpected response: %s', response.text)
  response_parsed = response.json()
  if 'main' not in response_parsed or 'temp' not in response_parsed['main']:
    logging.exception('Expected fields not in response: %s', response.text)
  return response_parsed['main']
