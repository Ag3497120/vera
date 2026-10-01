#!/usr/bin/env python3
"""Read-only current-index diagnostic; no accuracy/generalization claim."""
import argparse
import json
from pathlib import Path
import sys
import time
from round5a_support import environment, hashes, write
from verantyx.paths import corpus_root
from verantyx.one import Vera

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--root',type=Path,default=corpus_root()/'build/round3');args=parser.parse_args()
    if sys.version_info[:2]!=(3,11):raise SystemExit('Python3.11 required')
    if any(s in str(args.root).lower() for s in ('sealed','heldout')):raise SystemExit('public existing indexes only')
    args.output.mkdir(parents=True,exist_ok=False);write(args.output/'environment.json',environment())
    def assets():
        return {str(p):{'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns} for f in ('general_qa','local','pro','jawiki')
                for name in ('evidence.db','evidence.pkl') if (p:=args.root/f/'evidence'/name).exists()}
    before=assets();h=hashes();started=time.perf_counter();v=Vera(mode='semantic',round3_root=args.root)
    initialization=(time.perf_counter()-started)*1000;rows=[]
    try:
        for q in ('日本の首都はどこ？','富士山の高さは何m？'):
            started=time.perf_counter();a=v.ask(q);elapsed=(time.perf_counter()-started)*1000
            r={'question':q,'ask_ms':elapsed,'answer':a};rows.append(r)
            print(q,a['verdict'],round(elapsed,3),'ms',flush=True)
    finally:v.close()
    write(args.output/'result.json',{'root':str(args.root),'initialization_ms':initialization,'rows':rows,
                                    'assets_before':before,'assets_after':assets(),'metadata_unchanged':before==assets(),
                                    'runtime_hashes_before':h,'runtime_hashes_after':hashes(),
                                    'limitation':'Existing-index connection diagnostic only; no externally audited QA oracle.'})

if __name__=='__main__':main()
