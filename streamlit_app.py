"""Entrada do Streamlit Community Cloud.

O app mora em automacao/dashboard; este arquivo só ajusta o sys.path e chama main.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "automacao"))

from dashboard.app import main

main()
