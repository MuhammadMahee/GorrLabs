import sys
from pathlib import Path

# Add the nested directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "Downloads" / "GorrLabs-main"))

# Import the Flask app
from api.index import app

__all__ = ['app']

