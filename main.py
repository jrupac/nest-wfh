"""
Nest-WFH is a project that aims to prevent your Nest thermostat from going into
auto-away mode if your phone is also at home.

The program works by querying to see if your phone's MAC address appears on the
network. If so, it will manually set all thermostats to "home". This is meant
to be run as a cron job.
"""

__author__ = 'ajay@roopakalu.com (Ajay Roopakalu)'

import requests
import nmap
import subprocess

import keys

STRUCTURE_URL = 'https://developer-api.nest.com/structures/'
THERMOSTATS_URL = 'https://developer-api.nest.com/devices/thermostats/'

STATUS_HOME = '"home"'
STATUS_AWAY = '"away"'


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


def main():
  thermostat_model = GetAllThermostats(keys.ACCESS_TOKEN)
  structure_ids = GetStructureIds(thermostat_model)

  if IsReferenceDeviceOnNetwork(
      keys.PRIVATE_IP_SUBNET, keys.DEVICE_MAC_ADDRESS):
    print 'Device found on network; set status to HOME'
    print SetAwayStatus(keys.ACCESS_TOKEN, structure_ids, status=STATUS_HOME)
  else:
    print 'No device found on network; set status to AWAY'
    print SetAwayStatus(keys.ACCESS_TOKEN, structure_ids, status=STATUS_AWAY)


if __name__ == '__main__':
  main()
