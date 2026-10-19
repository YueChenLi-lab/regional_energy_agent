"""Competition entry alias; app.py uses the same console, legacy_app.py keeps the original UI."""
from pathlib import Path

from dotenv import load_dotenv

from energy_agent.console.app import main

load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
main()
