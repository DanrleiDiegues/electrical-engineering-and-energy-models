"""Entrada do Streamlit Cloud sem espaços no caminho de implantação."""
from pathlib import Path
import runpy
import sys

APP_DIR = Path(__file__).resolve().parent / "05. PLANEJAMENTO ENERGÉTICO" / "hidrotermico-streamlit"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
runpy.run_path(str(APP_DIR / "app.py"), run_name="__main__")
