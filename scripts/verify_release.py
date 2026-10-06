"""Verify declared release-file hashes without reading private data or the network."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from oart_analysis.release import verify_release


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--strict',action='store_true',help='Include generated files; use on a pristine extraction.')
    args=parser.parse_args(argv)
    root=args.root.resolve()
    try:
        result=verify_release(root,strict=args.strict)
        print(json.dumps(result,indent=2))
        return 0 if result['passed'] else 1
    except (OSError,ValueError,KeyError) as error:
        parser.exit(1,f'ERROR: {error}\n')


if __name__=='__main__':raise SystemExit(main())
