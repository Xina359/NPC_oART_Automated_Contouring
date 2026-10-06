"""Run the English-only public-package text/path check from a repository checkout."""
from pathlib import Path
import sys

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from oart_analysis.release_hygiene import main

if __name__ == '__main__':
    raise SystemExit(main(['--root', str(ROOT), *sys.argv[1:]]))
