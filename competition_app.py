"""Optional competition presentation; the original app.py remains available."""
from pathlib import Path

from dotenv import load_dotenv

from energy_agent.console.app import main

load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
main()
