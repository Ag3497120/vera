"""Immutable run recording shared by the Round5-A reproduction CLIs."""
import datetime
import hashlib
import json
import os
import platform
import resource
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
RUNTIME=tuple(sorted(p for p in (ROOT/'verantyx').rglob('*')
                     if p.is_file() and p.suffix in ('.py','.json','.html')
                     and '__pycache__' not in p.parts))

def hashes():return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in RUNTIME}
def write(path,value):
    with Path(path).open('x') as stream:json.dump(value,stream,ensure_ascii=False,indent=2);stream.write('\n')
def memory_bytes():
    n=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return n if sys.platform=='darwin' else n*1024
def environment():
    process_error=None
    try:
        snapshot=subprocess.run(['ps','-axo','pid,command'],capture_output=True,text=True,timeout=5)
        processes=snapshot.stdout if snapshot.returncode == 0 else ''
        if snapshot.returncode:process_error=snapshot.stderr.strip() or 'ps returned '+str(snapshot.returncode)
    except (OSError, subprocess.TimeoutExpired) as exc:
        processes='';process_error=str(exc)
    return {'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'python':sys.version,
            'executable':sys.executable,'realpath':str(Path(sys.executable).resolve()),'platform':platform.platform(),
            'cwd':str(ROOT),'model_instruction':'gpt-6.1-sol/max/FAST(priority)','runtime_llm':False,
            'sealed_evaluation':False,'preregistration_commit':'bdb454f',
            'process_observation_error':process_error,
            'parallel_corpus_processes':None if process_error else [s for s in processes.splitlines() if ('vera-corpus' in s or 'wiki_local_worker.py' in s) and 'round5a_' not in s],
            'parallel_verification_processes':None if process_error else [s for s in processes.splitlines() if 'guard/verify_all.py' in s],
            'runtime_hashes':hashes(),'peak_rss_bytes':memory_bytes()}
