"""
Application entry point.
"""

__author__ = 'ajay@roopakalu (Ajay Roopakalu)'

from flask import Flask

app = Flask(__name__)

@app.route('/')
def index():
  return 'Hello World!'

def main():
  app.run()


if __name__ == '__main__':
  main()