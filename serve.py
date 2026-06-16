"""Start the DataMind Studio server."""
import os
import sys

# Set project root to current directory
project_root = os.path.dirname(os.path.abspath(__file__))

from datamind.api.app import create_app
app = create_app(project_root)
