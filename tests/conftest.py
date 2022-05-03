import sys
from os.path import abspath, dirname
import os

root_dir = dirname(dirname(abspath(__file__)))
sys.path.append(root_dir)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


pytest_plugins = [
    'tests.fixtures.fixture_data'
]
