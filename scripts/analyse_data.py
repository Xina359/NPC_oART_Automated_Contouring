"""Run the analyse pipeline; see README.md for arguments."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from oart_analysis.cli import main

if __name__ == '__main__':
    raise SystemExit(main(['analyse', *sys.argv[1:]]))
