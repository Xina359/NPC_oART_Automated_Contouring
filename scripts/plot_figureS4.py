"""Plot S4; old S selectors map to the corresponding Extended Data number."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from oart_analysis.cli import main
if __name__=='__main__':raise SystemExit(main(['plot','--figure','S4',*sys.argv[1:]]))
