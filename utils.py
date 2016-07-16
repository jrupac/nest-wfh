"""
Common utilities.
"""
__author__ = 'ajay@roopakalu.com (Ajay Roopakalu)'

import subprocess

import nmap

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