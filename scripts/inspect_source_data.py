"""Read-only workbook structure and source-revision inspection (no statistics)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from oart_analysis.cli import main
if __name__ == '__main__':
    raise SystemExit(main(['inspect-source', *sys.argv[1:]]))
