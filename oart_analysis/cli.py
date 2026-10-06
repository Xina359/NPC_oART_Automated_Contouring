"""Explicit bundled and workbook input modes with Extended Data output names.

An explicitly selected workbook never falls back to bundled records.
Output directories must be empty to prevent mixed data provenance."""
from __future__ import annotations
import argparse
import importlib.metadata
import platform
from pathlib import Path
import sys
import zipfile
from xml.etree import ElementTree as ET
from . import __version__
from .constants import FIGURES,ALIASES
from .io import read_source,write_csv,write_json


def _runtime_versions(imaging=False):
    names = ['numpy', 'scipy', 'matplotlib', 'Pillow']
    if imaging:
        names.extend(['SimpleITK', 'pydicom'])
    versions = {}
    for name in names:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return {'python': platform.python_version(), 'platform': platform.platform(),
            'code': __version__, 'packages': versions}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('all','analyse','plot','extract','export-bundled','metrics','sample-size','inspect-source'))
    parser.add_argument('--source-data',type=Path,help='Explicit local Source_data.xlsx; never auto-discovered')
    parser.add_argument('--strategy-sheet',help='Exact GTVn worksheet tab override; schema is validated and input is not renamed')
    parser.add_argument('--output',type=Path,default=Path('outputs'),help='New/empty output directory; existing files are not overwritten')
    parser.add_argument('--figure',choices=(*FIGURES,*ALIASES),help='ED4-ED7 are canonical; S4-S7 are compatibility aliases')
    parser.add_argument('--config',type=Path,default=Path('config/imaging.local.json'))
    args=parser.parse_args(argv)
    if args.strategy_sheet is not None and (args.source_data is None or args.command in ('metrics','sample-size')):
        parser.error('--strategy-sheet requires --source-data and a workbook command')
    if args.command=='sample-size':
        from .statistics import precision_sample_size
        import json
        print(json.dumps(precision_sample_size(),indent=2));return 0
    if args.command=='plot' and args.figure is None:parser.error('plot requires --figure')
    if args.figure is not None and args.command!='plot':parser.error('--figure applies only to plot')
    if args.command in ('analyse','extract','export-bundled','inspect-source') and args.source_data is None:
        parser.error(f'{args.command} requires --source-data; the bundled subset cannot support full patient-level reanalysis or full S6')
    if args.source_data and args.source_data.resolve().is_relative_to(args.output.resolve()):
        parser.error('Keep the input workbook outside the output directory')
    if args.source_data and not args.source_data.is_file():parser.error(f'Input workbook not found: {args.source_data}; no fallback to bundled data')
    if args.output.exists() and (not args.output.is_dir() or any(args.output.iterdir())):
        parser.error('Output directory must be empty; choose a new --output path to avoid mixing provenance')
    try:
        if args.command=='metrics':
            if args.source_data:parser.error('metrics uses local images via --config, not --source-data')
            from .imaging import evaluate_config
            count=evaluate_config(args.config,args.output)
            write_json(_runtime_versions(imaging=True),args.output/'runtime_versions.json')
            print(f'Evaluated {count} local ROI pairs.');return 0
        from .plot_data import load_bundled,from_workbook,validate,export_bundle
        if args.source_data is not None:
            print(f'Data mode: local workbook ({args.source_data.name}).',flush=True)
            source=read_source(args.source_data, strategy_sheet=args.strategy_sheet)
            for warning in source['metadata']['readme_warnings']:print(f'Metadata warning: {warning}',file=sys.stderr)
            print(f"GTVn worksheet: {source['metadata']['strategy_worksheet']}; "
                  f"source profile: {source['metadata']['source_profile_match']['status']}.",flush=True)
            if args.command=='inspect-source':
                report={**source['metadata'], 'code_version':__version__, 'input_mode':'workbook',
                    'full_patient_level_analysis':False, 'complete_S6_available':False,
                    'scope':'worksheet structure, metadata and version identity; no statistical reanalysis',
                    'parsed_rows':{name:len(rows) for name,rows in source.items() if isinstance(rows,list)}}
                write_json(report,args.output/'source_inspection.json')
                print(f'Inspected input without modifying it: {args.output}');return 0
            if args.command=='extract':
                # This is an explicit LOCAL export, not a public-release bundle.
                for name,rows in source.items():
                    if isinstance(rows,list):
                        filename=name.replace(' ','_').replace('/','_')+'.csv';write_csv(rows,args.output/filename)
                write_json({**source['metadata'],'input_mode':'workbook','full_patient_level_analysis':False,
                    'purpose':'local extraction only; not automatically authorized for public redistribution'},args.output/'data_source.json')
                return 0
            from .analysis import analyse
            # Export-bundled uses a separate sibling analysis folder so the bundle remains clean.
            if args.command=='export-bundled':
                import tempfile
                with tempfile.TemporaryDirectory(prefix='oart-bundle-validation-') as tmp:
                    report=analyse(source,Path(tmp))
                data,provenance=from_workbook(source,True);export_bundle(data,provenance,args.output)
                print('Exported exactly six public plotting CSVs and manifest; full workbook excluded.');return 0
            report=analyse(source,args.output/'analysis');data,provenance=from_workbook(source,True)
            print(f"Verified {report['paired_comparisons']} paired comparisons and generated {report['S6_rows']} S6 rows.",flush=True)
        else:
            print('Data mode: bundled plotting subset. Full patient-level analysis and complete S6 are NOT performed.',flush=True)
            data,provenance=load_bundled()
        provenance.update(code_version=__version__,command=args.command,figure=ALIASES.get(args.figure,args.figure),validation=validate(data))
        write_json(provenance,args.output/'data_source.json')
        if args.command in ('all','plot'):
            from .plotting import render
            for figure in FIGURES if args.command=='all' else (args.figure,):
                canonical=ALIASES.get(figure,figure)
                if canonical!=figure:print(f'Legacy selector {figure} maps to {canonical}; output uses Extended Data naming.')
                print(f'Rendering {canonical}...',flush=True)
                folder=render(data,canonical,args.output/'figures');write_json(provenance,folder/'data_source.json')
        write_json(_runtime_versions(),args.output/'runtime_versions.json')
        print(f'Completed: {args.output}');return 0
    except (ValueError,FileNotFoundError,KeyError,ImportError,OSError,RuntimeError,zipfile.BadZipFile,ET.ParseError) as exc:
        print(f'ERROR: {exc}',file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
