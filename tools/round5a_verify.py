#!/usr/bin/env python3
"""Separated kernel, reader, public route, adapter, and safe compatibility gates."""
import argparse
import subprocess
import sys
from pathlib import Path
from round5a_support import ROOT, environment, hashes, write

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--compatibility-from',type=Path);args=parser.parse_args()
    if sys.version_info[:2]!=(3,11):raise SystemExit('Final gates require Python3.11')
    args.output.mkdir(parents=True,exist_ok=False);before=hashes();write(args.output/'environment.json',environment())
    groups={'kernel':['tests/test_semantic_kernel.py'],'reader':['tests/test_semantic_reader.py'],
            'public':['tests/test_semantic_public.py'],'adapter':['tests/test_semantic_retrieve.py'],
            'compatibility':['tests/test_question.py','tests/test_answer.py','tests/test_library.py','tests/test_round4.py']}
    results={}
    for name,files in groups.items():
        if name=='compatibility' and args.compatibility_from:
            import json
            prior=json.loads((args.compatibility_from/'gates.json').read_text())
            legacy=tuple(p for p in before if not Path(p).name.startswith('semantic'))
            if (not prior['source_unchanged'] or prior['groups']['compatibility']['exit_code']!=0 or
                any(prior['runtime_hashes_after'].get(p)!=before[p] for p in legacy)):
                raise SystemExit('Unchanged legacy entry files and passed compatibility required')
            results[name]={**prior['groups'][name],'reused_from':str(args.compatibility_from),
                           'reason':'All non-semantic runtime sources and packaged data are byte-identical.'}
            print(name,results[name]['summary'],'(reused unchanged legacy result)',flush=True);continue
        cmd=[sys.executable,'-m','pytest','-q',*files,'--basetemp='+str(args.output/(name+'-tmp'))]
        r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
        (args.output/(name+'.stdout')).write_text(r.stdout);(args.output/(name+'.stderr')).write_text(r.stderr)
        results[name]={'command':cmd,'exit_code':r.returncode,'summary':r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr}
        print(name,results[name]['summary'],flush=True)
    payload={'groups':results,'passed':all(r['exit_code']==0 for r in results.values()),
             'runtime_hashes_before':before,'runtime_hashes_after':hashes(),'source_unchanged':before==hashes()}
    write(args.output/'gates.json',payload)
    return 0 if payload['passed'] and payload['source_unchanged'] else 1

if __name__=='__main__':raise SystemExit(main())
