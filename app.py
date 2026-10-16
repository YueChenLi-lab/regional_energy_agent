"""Run with: python -m streamlit run app.py."""
from pathlib import Path

from dotenv import load_dotenv

from energy_agent.ui import main

load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
main()
