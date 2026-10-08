"""Bounded observations of an artifact, never a correctness certificate.

macOS Seatbelt is the security boundary.  AST/token checks only reduce the
accepted pure fragment; they are not advertised as an OS sandbox.  If Seatbelt
or any required resource limit cannot be installed, no artifact is executed.
Calls are sequential and use the requested interface. Python/SQL witnesses may
share a bounded child, with fresh namespaces/builtins/inputs or memory DBs.
Node uses fresh processes. Fork-capable shell requests are held until their
descendants outside the owned process group can be accounted for.
The caller must charge these observations to its public-request budget.
"""
from __future__ import annotations

import ast
import ctypes
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import select
import selectors
import shlex
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import threading
import time
from typing import Any

from .contract_ir import ContractError

PYTHON = "/opt/homebrew/bin/python3.11"
NODE = "/opt/homebrew/bin/node"
SEATBELT = "/usr/bin/sandbox-exec"
PROFILES = frozenset({"python_pure_v1", "node_commonjs_sync_v1",
                      "sqlite_select_v1", "posix_numeric_stream_v1"})
MAX_SOURCE_BYTES = 65536
MAX_CASES = 12
MAX_CHILD_MS = 200
MAX_CALL_MS = 1000
MAX_OUTPUT_BYTES = 1048576
MAX_INPUT_BYTES = 262144
_LOCK = threading.Lock()
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,31}\Z")
_MEMORY_LIMIT = 536870912

# Shell builtins install hard/soft limits without starting a second Python.
# The command is supplied only as positional argv, never interpolated as code.
_RESOURCE_BOOTSTRAP = '''
ulimit -t 1 && ulimit -f 0 && ulimit -c 0 && ulimit -n 64 && ulimit -u 1024 || {
    printf 'RESOURCE_LIMIT_UNAVAILABLE' >&2
    exit 78
}
exec "$@"
'''


class _Usage(ctypes.Structure):
    # SDK sys/resource.h rusage_info_v2, unchanged prefix since macOS 10.9.
    _fields_ = [('uuid', ctypes.c_ubyte * 16)] + [(name, ctypes.c_uint64) for name in (
        'user_time', 'system_time', 'pkg_idle_wkups', 'interrupt_wkups', 'pageins',
        'wired_size', 'resident_size', 'phys_footprint', 'proc_start_abstime',
        'proc_exit_abstime', 'child_user_time', 'child_system_time',
        'child_pkg_idle_wkups', 'child_interrupt_wkups', 'child_pageins',
        'child_elapsed_abstime', 'diskio_bytesread', 'diskio_byteswritten')]


def _resident_tree(pid: int) -> tuple[int, int]:
    library = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
    library.proc_pid_rusage.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
    library.proc_listchildpids.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
    pending, seen, total = [pid], set(), 0
    while pending:
        current = pending.pop()
        if current in seen: continue
        seen.add(current)
        if len(seen) > 32: return total, len(seen)
        usage = _Usage()
        if library.proc_pid_rusage(current, 2, ctypes.byref(usage)) != 0:
            # A process can exit between enumeration and sampling.
            if ctypes.get_errno() == 3: continue
            raise OSError(ctypes.get_errno(), 'resident-size monitor is unavailable')
        total += usage.resident_size
        children = (ctypes.c_int * 33)()
        count = library.proc_listchildpids(current, children, ctypes.sizeof(children))
        if count < 0: raise OSError('child-process monitor is unavailable')
        pending.extend(child for child in children if child > 0)
    return total, len(seen)

_PROBE = r'''
import json, os, socket, subprocess, sys
p = json.load(sys.stdin)
checks = {}
for name, path, mode in [('external_read',p['read'],'r'),
                         ('external_write',p['write'],'w'),
                         ('local_write',p['local'],'w')]:
    try:
        with open(path, mode) as handle:
            if mode == 'r': handle.read(1)
        checks[name] = False
    except PermissionError:
        checks[name] = True
    except OSError:
        checks[name] = False
try:
    sock = socket.socket()
    sock.settimeout(.02)
    sock.connect(('127.0.0.1', 9))
    checks['network'] = False
except PermissionError:
    checks['network'] = True
except OSError:
    checks['network'] = False
finally:
    if 'sock' in locals(): sock.close()
try:
    child=os.fork()
except PermissionError:
    checks['fork_denied']=True
except OSError:
    checks['fork_denied']=False
else:
    if child==0: os._exit(0)
    os.waitpid(child,0)
    checks['fork_denied']=False
try:
    subprocess.run(['/usr/bin/true'], check=False, timeout=.02)
    checks['unlisted_exec'] = False
except PermissionError:
    checks['unlisted_exec'] = True
except (OSError, subprocess.TimeoutExpired):
    checks['unlisted_exec'] = False
print(json.dumps({'checks':checks,'verified':all(checks.values())}))
'''

_PY_RUNNER = r'''
import contextlib, copy, inspect, io, json, math, sys
payload = json.load(sys.stdin)
source = open(sys.argv[1], encoding='utf8').read()
interface, case = payload['interface'], payload['case']
args, kwargs = case.get('args', []), case.get('kwargs', {})
before = copy.deepcopy({'args':args, 'kwargs':kwargs})
budget = [payload['output_limit']]
class OutputLimit(Exception): pass
class Capture(io.TextIOBase):
    def __init__(self): self.parts = []
    def write(self, value):
        length = len(value.encode('utf8'))
        if length > budget[0]: raise OutputLimit('captured output exceeds byte limit')
        budget[0] -= length
        self.parts.append(value)
        return len(value)
    def flush(self): pass
    def getvalue(self): return ''.join(self.parts)
def typed(value, depth=0):
    if depth > 16: raise ValueError('return nesting exceeds profile')
    t = type(value)
    if t is type(None): return {'type':'null','value':None}
    if t is bool: return {'type':'bool','value':value}
    if t is int: return {'type':'int','value':value}
    if t is float:
        if not math.isfinite(value): return {'type':'nonfinite_float','value':repr(value)}
        return {'type':'float','value':value}
    if t is str: return {'type':'str','value':value}
    if t is list: return {'type':'list','items':[typed(v,depth+1) for v in value]}
    if t is dict:
        if any(type(k) is not str for k in value):
            return {'type':'unsupported_dict_keys'}
        return {'type':'dict','fields':{k:typed(v,depth+1) for k,v in value.items()}}
    return {'type':'unsupported','python_type':t.__name__}
out, err = Capture(), Capture()
result = {'status':'EXECUTED','signature':None,'signature_matches':False}
try:
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        namespace = {'__name__':'__vera_artifact__'}
        exec(compile(source, sys.argv[1], 'exec'), namespace)
        fn = namespace.get(interface['name'])
        if not callable(fn): raise ValueError('requested function is absent')
        signature = inspect.signature(fn)
        parameters = [{'name':p.name,'kind':p.kind.name,'has_default':p.default is not inspect.Parameter.empty}
                      for p in signature.parameters.values()]
        result['signature'] = parameters
        wanted = [{'name':name,'kind':'POSITIONAL_OR_KEYWORD','has_default':False}
                  for name in interface.get('parameters',[]) if name not in interface.get('keyword_only',[])]
        wanted += [{'name':name,'kind':'KEYWORD_ONLY','has_default':False}
                   for name in interface.get('keyword_only',[])]
        result['signature_matches'] = parameters == wanted and not inspect.iscoroutinefunction(fn)
        # Calling the actual interface even on mismatch yields an observation,
        # never a repaired wrapper.  A verifier must reject the mismatch.
        value = fn(*args, **kwargs)
        result['typed_value'] = typed(value)
        if result['typed_value']['type'] not in ('unsupported','unsupported_dict_keys','nonfinite_float'):
            json.dumps(value, allow_nan=False)
            result['value'] = value
except OutputLimit as error:
    result.update(status='OUTPUT_LIMIT', error=str(error))
except BaseException as error:
    result.update(status='ARTIFACT_ERROR', error_type=type(error).__name__, error=str(error)[:1024])
result.update(stdout=out.getvalue(),stderr=err.getvalue(),
              mutation={'unchanged':typed(before) == typed({'args':args,'kwargs':kwargs}),
                        'before':before,'after':{'args':args,'kwargs':kwargs},
                        'typed_before':typed(before),'typed_after':typed({'args':args,'kwargs':kwargs})})
print(json.dumps(result,ensure_ascii=False,allow_nan=False,separators=(',',':')))
'''

_NODE_RUNNER = r'''
'use strict';
const fs = require('fs'), vm = require('vm');
const payload = JSON.parse(fs.readFileSync(0,'utf8'));
const source = fs.readFileSync(process.argv[2],'utf8');
const context = vm.createContext({}, {codeGeneration:{strings:false,wasm:false}});
// The input and module objects are constructed inside the new realm.
vm.runInContext('var module={exports:{}}; var exports=module.exports; var input=JSON.parse('+JSON.stringify(JSON.stringify(payload))+');',context);
// No host-realm function is passed into the context: even console methods are
// built inside it. A host function's constructor would bypass string-code
// generation restrictions in the VM's own realm.
const recorder=vm.runInContext(`(() => {
  const state={stdout:'',stderr:'',remaining:input.output_limit};
  function capture(channel, values) {
    const line=values.map(String).join(' ')+'\\n';
    const bytes=unescape(encodeURIComponent(line)).length;
    if(bytes>state.remaining) {const error=new Error('output exceeds byte limit');error.name='OutputLimit';throw error;}
    state.remaining-=bytes;state[channel]+=line;
  }
  return {console:Object.freeze({log:(...v)=>capture('stdout',v),error:(...v)=>capture('stderr',v),warn:(...v)=>capture('stderr',v)}),
          snapshot:()=>({stdout:state.stdout,stderr:state.stderr})};
})()`,context);
context.console=recorder.console;
function typed(value, depth=0) {
  if (depth>16) throw new Error('return nesting exceeds profile');
  if (value===undefined) return {type:'undefined'};
  if (value===null) return {type:'null',value:null};
  const t=typeof value;
  if (t==='number') return Number.isFinite(value) ? {type:'number',value:value,integer:Number.isInteger(value),safe_integer:Number.isSafeInteger(value)} : {type:'nonfinite_number',value:String(value)};
  if (t==='string'||t==='boolean') return {type:t,value:value};
  if (Array.isArray(value)) return {type:'array',items:Array.from({length:value.length},(_,i)=>i in value ? typed(value[i],depth+1) : {type:'hole'})};
  if (t==='object') return {type:'object',fields:Object.fromEntries(Object.keys(value).map(k=>[k,typed(value[k],depth+1)]))};
  return {type:'unsupported',js_type:t};
}
const result={status:'EXECUTED',signature:null,signature_matches:false};
let before=null;
try {
  before=typed(vm.runInContext('({args:input.case.args||[],kwargs:input.case.kwargs||{}})',context));
  vm.runInContext(source,context,{timeout:payload.timeout_ms});
  const fn=vm.runInContext('module.exports[input.interface.name]',context);
  result.export={name:payload.interface.name,present:typeof fn==='function',format:'commonjs'};
  if(typeof fn!=='function') throw new Error('requested CommonJS export is absent');
  const text=Function.prototype.toString.call(fn);
  const match=text.match(/^(?:async\s+)?function(?:\s+[A-Za-z_$][\w$]*)?\s*\(([^)]*)\)/)||text.match(/^(?:async\s+)?\(([^)]*)\)\s*=>/)||text.match(/^([A-Za-z_$][\w$]*)\s*=>/);
  const raw=match ? match[1].trim() : null;
  const params=raw===null ? null : raw==='' ? [] : raw.split(',').map(x=>x.trim());
  const simple=params!==null && params.every(x=>/^[A-Za-z_][A-Za-z0-9_]*$/.test(x));
  const sync=!/^async\s/.test(text);
  result.signature={parameters:params,arity:fn.length,sync:sync};
  result.signature_matches=simple&&sync&&JSON.stringify(params)===JSON.stringify(payload.interface.parameters||[])&&!(payload.interface.keyword_only||[]).length;
  if(Object.keys(payload.case.kwargs||{}).length) throw new Error('JavaScript kwargs are unsupported');
  const value=vm.runInContext('module.exports[input.interface.name](...(input.case.args||[]))',context,{timeout:payload.timeout_ms});
  if(value && typeof value.then==='function') throw new Error('Promise return is outside synchronous profile');
  result.typed_value=typed(value);
  if(!['undefined','unsupported','nonfinite_number'].includes(result.typed_value.type)) result.value=value;
} catch(error) { result.status=error.name==='OutputLimit'?'OUTPUT_LIMIT':'ARTIFACT_ERROR';result.error_type=error.name;result.error=String(error.message).slice(0,1024); }
try {
  const after=typed(vm.runInContext('({args:input.case.args||[],kwargs:input.case.kwargs||{}})',context,{timeout:payload.timeout_ms}));
  result.mutation={unchanged:JSON.stringify(before)===JSON.stringify(after),typed_before:before,typed_after:after};
} catch(error) { result.mutation={unchanged:false,error:'input snapshot failed'}; }
const observed=recorder.snapshot();
result.stdout=observed.stdout;result.stderr=observed.stderr;
process.stdout.write(JSON.stringify(result));
'''

_SQL_RUNNER = r'''
import json, sqlite3, sys
p=json.load(sys.stdin)
sql=open(sys.argv[1],encoding='utf8').read()
connection=sqlite3.connect(':memory:')
connection.enable_load_extension(False)
connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 1048576)
connection.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 65536)
connection.setlimit(sqlite3.SQLITE_LIMIT_COLUMN, 64)
def quote(name): return '"'+name.replace('"','""')+'"'
try:
    tables=p['case'].get('tables',{})
    for name,table in tables.items():
        schema=table.get('schema',table.get('columns',[]))
        definitions=[quote(column['name'])+' '+column['type']+('' if column.get('nullable',False) else ' NOT NULL') for column in schema]
        connection.execute('CREATE TABLE '+quote(name)+' ('+','.join(definitions)+')')
        connection.executemany('INSERT INTO '+quote(name)+' VALUES ('+','.join('?' for c in schema)+')',table.get('rows',[]))
    connection.commit()
    connection.execute('PRAGMA query_only=ON')
    def authorize(action,arg1,arg2,db,trigger):
        if action==sqlite3.SQLITE_READ: return sqlite3.SQLITE_OK if db=='main' and arg1 in tables else sqlite3.SQLITE_DENY
        if action in (sqlite3.SQLITE_SELECT,sqlite3.SQLITE_RECURSIVE): return sqlite3.SQLITE_OK
        if action==sqlite3.SQLITE_FUNCTION: return sqlite3.SQLITE_DENY if str(arg2).lower() in ('load_extension','readfile','writefile') else sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY
    connection.set_authorizer(authorize)
    cursor=connection.execute(sql)
    columns=[column[0] for column in cursor.description] if cursor.description else []
    rows=[list(row) for row in cursor.fetchmany(1025)]
    if len(rows)>1024: raise ValueError('output relation exceeds profile bound')
    def tag(v): return 'null' if v is None else 'integer' if type(v) is int else 'real' if type(v) is float else 'text' if type(v) is str else 'blob'
    result={'status':'EXECUTED','columns':columns,'rows':rows,'row_types':[[tag(v) for v in row] for row in rows],
            'schema_matches':columns==p['interface'].get('columns',[]),
            'stdout':'','stderr':'','mutation':{'unchanged':True,'enforced':'sqlite_read_authorizer'},
            'sqlite_version':sqlite3.sqlite_version}
except BaseException as error:
    result={'status':'ARTIFACT_ERROR','error_type':type(error).__name__,'error':str(error)[:1024],'stdout':'','stderr':''}
finally:
    connection.close()
print(json.dumps(result,ensure_ascii=False,allow_nan=False,separators=(',',':')))
'''


def _batch_program(profile: str) -> str:
    """Build only a trusted runner, without interpolating artifact/case code.

    Existing single-call observation bodies are reused, not their process or
    module state. Each invocation has fresh local helper classes/functions.
    """
    if profile == 'python_pure_v1':
        body = _PY_RUNNER.split("interface, case = payload['interface'], payload['case']\n", 1)[1]
        body = "interface, case = payload['interface'], copy.deepcopy(payload['case'])\n" + body
        body = body.replace("namespace = {'__name__':'__vera_artifact__'}",
                            "namespace = {'__name__':'__vera_artifact__', '__builtins__':dict(builtins_template)}")
        body = body.replace("exec(compile(source, sys.argv[1], 'exec'), namespace)",
                            "exec(compile(source, artifact_path, 'exec'), namespace)")
        body = body.replace("print(json.dumps(result,ensure_ascii=False,allow_nan=False,separators=(',',':')))",
                            "json.dumps(result,allow_nan=False)\nreturn result")
    elif profile == 'sqlite_select_v1':
        body = _SQL_RUNNER.split("connection=sqlite3.connect(':memory:')\n", 1)[1]
        body = "p=payload\nsql=source\nconnection=sqlite3.connect(':memory:')\n" + body
        body = body.replace("print(json.dumps(result,ensure_ascii=False,allow_nan=False,separators=(',',':')))",
                            "json.dumps(result,allow_nan=False)\nreturn result")
    else:
        raise ValueError('batch is registered only for Python/SQLite')
    function = '\n'.join('    '+line if line else '' for line in body.splitlines())
    imports = ("import builtins, contextlib, copy, inspect, io, json, math, sys\n"
               if profile == 'python_pure_v1' else "import builtins, copy, json, sqlite3, sys\n")
    return (imports +
            "def observe(payload, source, artifact_path, builtins_template):\n" + function + '\n' + r'''
controls, wire = sys.stdin, sys.stdout
envelope=json.loads(controls.readline())
artifact_path=sys.argv[1]
source=open(artifact_path,encoding='utf8').read()
builtins_template=dict(vars(builtins))
def emit(event,index=None,result=None):
    frame={'event':event}
    if index is not None: frame['index']=index
    if result is not None: frame['result']=result
    wire.write(json.dumps(frame,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n')
    wire.flush()
finished=0
for index,original_case in enumerate(envelope['cases']):
    emit('ready',index)
    permit_line=controls.readline()
    if not permit_line or json.loads(permit_line)!={'permit':index}:
        raise ValueError('missing or wrong case permit')
    emit('started',index)
    payload={'case':copy.deepcopy(original_case),'interface':copy.deepcopy(envelope['interface']),
             'output_limit':envelope['output_limit']}
    try:
        result=observe(payload,source,artifact_path,builtins_template)
    except BaseException as error:
        result={'status':'ARTIFACT_ERROR','error_type':type(error).__name__,'error':str(error)[:1024],
                'stdout':'','stderr':'','observation_failed':True}
    emit('result',index,result)
    finished+=1
    if result['status']!='EXECUTED': break
emit('done',result={'finished':finished})
''')


class _ProtocolError(Exception):
    pass


class _BatchProtocol:
    """Parent-owned counters; a permit reservation is not an observed call."""
    def __init__(self, count: int, before_case: Any = None):
        self.count, self.before_case = count, before_case
        self.pending = bytearray()
        self.results: list[dict] = []
        self.reserved = self.attempted = self.finished = 0
        self.current = None
        self.started = False
        self.done = False
        self.hook_error = None
        self.trace: list[dict] = []

    def feed(self, chunk: bytes) -> bytes:
        self.pending.extend(chunk)
        permits = bytearray()
        while b'\n' in self.pending:
            line, _, rest = self.pending.partition(b'\n')
            self.pending[:] = rest
            try: frame = json.loads(line)
            except (ValueError, UnicodeError): raise _ProtocolError('non-JSON batch frame')
            if not isinstance(frame,dict) or self.done: raise _ProtocolError('unexpected batch frame')
            event, index = frame.get('event'), frame.get('index')
            if event == 'ready':
                if (type(index) is not int or index != self.finished or self.current is not None or index >= self.count
                        or (self.results and self.results[-1]['status']!='EXECUTED')):
                    raise _ProtocolError('out-of-order case permit request')
                if self.before_case is not None:
                    try: self.before_case()
                    except BaseException as error:
                        self.hook_error=error
                        raise
                self.reserved += 1
                self.current, self.started = index, False
                permits.extend(json.dumps({'permit':index}).encode()+b'\n')
            elif event == 'started':
                if type(index) is not int or self.current != index or self.started: raise _ProtocolError('unpermitted or duplicate case start')
                self.started = True
                self.attempted += 1
            elif event == 'result':
                row = frame.get('result')
                if type(index) is not int or self.current != index or not self.started or not isinstance(row,dict) or 'status' not in row:
                    raise _ProtocolError('case result without matching start')
                self.results.append(dict(row,index=index))
                self.finished += 1
                self.current, self.started = None, False
            elif event == 'done':
                if self.current is not None or frame.get('result') != {'finished':self.finished}:
                    raise _ProtocolError('inconsistent batch completion')
                self.done = True
            else: raise _ProtocolError('unknown batch event')
            self.trace.append({'event':event,'index':index})
        return bytes(permits)

    def complete(self) -> None:
        if self.pending or not self.done or self.current is not None:
            raise _ProtocolError('unfinished batch protocol')

    def stats(self) -> dict:
        return {'cases_reserved':self.reserved,'cases_attempted':self.attempted,
                'cases_finished':self.finished,'cases':self.attempted,
                'unconfirmed_starts':self.reserved-self.attempted}


def _reason(profile: str, source: Any, status: str, reason: str) -> dict:
    try: digest = hashlib.sha256(source.encode("utf-8")).hexdigest() if isinstance(source, str) else None
    except UnicodeEncodeError: digest = None
    return {"status": status, "reason": reason, "profile": profile,
            "development_revision":"r3",
            "artifact_sha256": digest, "results": [],
            "isolation": {"backend": "macos_seatbelt", "verified": False},
            "stats": {"launches": 0, "cases": 0, "cases_reserved":0,
                      "cases_attempted":0,"cases_finished":0,"unconfirmed_starts":0,
                      "output_bytes": 0, "output_reserved_bytes":0,
                      "children":[],"elapsed_ms": 0.0}, "trace":[],
            "correctness": "not_established_by_execution"}


def _validate(profile: str, source: str, interface: dict, cases: list) -> str | None:
    if profile not in PROFILES: return "unknown execution profile"
    if not isinstance(source, str): return "source must be text"
    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES: return "artifact exceeds 64 KiB"
    if not isinstance(interface, dict) or not isinstance(cases, list): return "interface/cases have wrong container types"
    if not cases or len(cases) > MAX_CASES: return "requires 1..12 witness cases"
    if profile in ("python_pure_v1", "node_commonjs_sync_v1"):
        if not isinstance(interface.get('parameters',[]),(list,tuple)): return 'parameters must be an ordered sequence'
        names = [interface.get("name")] + list(interface.get("parameters", []))
        if any(not isinstance(name, str) or not _IDENTIFIER.fullmatch(name) for name in names): return "invalid requested identifier"
        if len(set(names[1:])) != len(names[1:]): return "duplicate requested parameter"
        if not isinstance(interface.get('keyword_only',[]),(list,tuple)) or any(name not in names[1:] for name in interface.get('keyword_only',[])): return "keyword_only must be a subset of parameters"
    try:
        if len(json.dumps({"interface": interface, "cases": cases}, ensure_ascii=False, allow_nan=False).encode("utf-8")) > MAX_INPUT_BYTES:
            return "case payload exceeds input byte bound"
    except (ValueError, TypeError, RecursionError): return "cases must be finite JSON values"
    for case in cases:
        if not isinstance(case, dict): return "each case must be a dictionary"
        if not isinstance(case.get("args", []), list) or not isinstance(case.get("kwargs", {}), dict): return "args/kwargs must be list/dict"
        if profile in ('python_pure_v1','node_commonjs_sync_v1'):
            inputs = case.get('args',[]) + list(case.get('kwargs',{}).values())
            if len(inputs) > 4: return 'at most two collection inputs and two scalar parameters'
            collections = [value for value in inputs if isinstance(value,(list,dict))]
            if len(collections) > 2: return 'at most two collection inputs'
            for value in collections:
                if isinstance(value,list) and len(value) > 32: return 'input collection exceeds 32 elements'
                records = value if isinstance(value,list) else [value]
                if any(isinstance(item,(list,dict)) and (isinstance(item,list) or len(item)>6 or any(isinstance(field,(dict,list)) for field in item.values())) for item in records):
                    return 'requires flat records of at most six fields'
        if profile == "posix_numeric_stream_v1":
            if not isinstance(case.get("stdin", ""), str) or not isinstance(case.get("argv", []), list): return "stdin/argv have wrong types"
            argv, stream = case.get("argv", []), case.get("stdin", "")
            if len(argv) > 2 or any(not isinstance(arg, str) or re.fullmatch(r"0|-?[1-9][0-9]*", arg) is None for arg in argv): return "argv must contain at most two canonical integer strings"
            lines = stream.splitlines(keepends=True)
            if len(lines) > 32 or any(re.fullmatch(r"(?:0|-?[1-9][0-9]*)\n", line) is None for line in lines): return "stdin must contain at most 32 canonical integer lines including final newline"
        if profile == "sqlite_select_v1":
            tables = case.get("tables", {})
            if not isinstance(tables, dict) or not 1 <= len(tables) <= 2: return "SQL requires one or two explicit tables"
            for name, table in tables.items():
                if not isinstance(name, str) or not _IDENTIFIER.fullmatch(name) or not isinstance(table, dict): return "invalid SQL table"
                schema, rows = table.get("schema", table.get("columns", [])), table.get("rows", [])
                if not isinstance(schema, list) or not 1 <= len(schema) <= 6 or not isinstance(rows, list) or len(rows) > 32: return "SQL schema/row bounds exceeded"
                for column in schema:
                    if not isinstance(column, dict) or not _IDENTIFIER.fullmatch(str(column.get("name", ""))) or column.get("type") not in ("INTEGER", "REAL", "TEXT"):
                        return "invalid SQL column declaration"
                if len({column['name'] for column in schema}) != len(schema): return "duplicate SQL column"
                for row in rows:
                    if not isinstance(row, list) or len(row) != len(schema): return "SQL row does not match explicit schema"
                    for value, column in zip(row, schema):
                        if value is None:
                            if not column.get("nullable", False): return "null in a nonnullable input column"
                        elif column['type'] == 'INTEGER' and type(value) is not int: return "INTEGER input must be int, excluding bool"
                        elif column['type'] == 'REAL' and type(value) is not float: return "REAL input must be float"
                        elif column['type'] == 'TEXT' and type(value) is not str: return "TEXT input must be string"
    return None


def _source_gate(profile: str, source: str) -> str | None:
    if profile == "python_pure_v1":
        try: tree = ast.parse(source)
        except (SyntaxError, RecursionError) as error: return "invalid Python syntax: " + str(error)
        forbidden = {"open", "exec", "eval", "compile", "getattr", "setattr", "delattr", "globals", "locals", "vars", "breakpoint", "input", "help", "quit", "exit", "os", "sys", "socket", "subprocess", "ctypes"}
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom, ast.AsyncFunctionDef, ast.Await, ast.ClassDef)):
                return "imports/async/classes are outside the pure runner fragment"
            if isinstance(node, ast.Name) and (node.id in forbidden or node.id.startswith("__")): return "unsafe Python name: " + node.id
            if isinstance(node, ast.Attribute) and (node.attr.startswith("_") or node.attr in forbidden): return "unsafe Python attribute: " + node.attr
    elif profile == "node_commonjs_sync_v1":
        # This is an intentionally conservative acceptance gate, not a parser
        # or the security boundary.  It can refuse harmless quoted tokens.
        if re.search(r"\b(?:require|process|eval|Function|WebAssembly|import|fetch|XMLHttpRequest|constructor|prototype|__proto__)\b", source):
            return "unsafe or unsupported JavaScript capability"
    elif profile == "posix_numeric_stream_v1":
        try: tokens = shlex.split(source, posix=True)
        except ValueError as error: return "invalid shell quoting: " + str(error)
        # Single foreground numeric pipeline. Quoted awk programs remain one
        # token and may contain loops/semicolons without becoming shell code.
        lexer = shlex.shlex(source, posix=True, punctuation_chars="\n;&|<>()")
        lexer.whitespace = ' \t\r'
        lexer.whitespace_split = True
        lexer.commenters = "#"
        try: words = list(lexer)
        except ValueError as error: return str(error)
        if "`" in source or "$(" in source or any(w and all(c in '\n;&|<>()' for c in w) and w.strip('\n;') not in ('','|') for w in words): return "shell substitutions/background/redirection are forbidden"
        if any(re.search(r'\b(?:system|getline)\b', word.replace('\\\n','')) for word in words): return "awk external execution/read is forbidden"
        commands = []
        start = True
        for word in words:
            if word == "|" or not word.strip('\n;'): start = True; continue
            if start:
                if word in ('LC_ALL=C','LANG=C'): continue
                commands.append(word); start = False
        if not commands or any(command not in ("awk", "sort", "uniq", "/usr/bin/awk", "/usr/bin/sort", "/usr/bin/uniq") for command in commands):
            return "shell accepts only awk/sort/uniq numeric commands"
    return None


def _python_binary() -> str:
    binary = Path(PYTHON).resolve()
    app = binary.parent.parent / 'Resources/Python.app/Contents/MacOS/Python'
    return str(app) if app.is_file() else PYTHON


def _runtime_paths(profile: str = 'python_pure_v1') -> tuple[list[str], list[str]]:
    # Resolve only installed runtime directories; never grant a home directory.
    python = Path(PYTHON).resolve()
    python_version = python.parent.parent
    node = Path(NODE).resolve()
    libraries = [str(python_version)]
    if profile == 'node_commonjs_sync_v1': libraries.append(str(node.parent.parent / 'lib'))
    for name in (("llhttp", "libuv", "ada-url", "simdjson", "brotli", "c-ares", "hdrhistogram_c", "merve", "nbytes", "libnghttp2", "libnghttp3", "libngtcp2", "sqlite", "uvwasi", "zstd", "openssl@3", "icu4c@78") if profile == 'node_commonjs_sync_v1' else ()):
        path = Path("/opt/homebrew/opt") / name / "lib"
        if path.exists(): libraries.append(str(path.resolve()))
    for name in ("openssl@3", "sqlite", "gettext", "xz", "mpdecimal", "readline"):
        path = Path("/opt/homebrew/opt") / name / "lib"
        if path.exists(): libraries.append(str(path.resolve()))
    python_app = python_version / 'Resources/Python.app/Contents/MacOS/Python'
    binaries = [PYTHON, str(python), str(python_app), SEATBELT]
    if profile == 'node_commonjs_sync_v1': binaries += [NODE,str(node)]
    if profile == 'posix_numeric_stream_v1': binaries += ["/bin/sh", "/bin/bash", "/usr/bin/awk", "/usr/bin/sort", "/usr/bin/uniq"]
    return sorted(set(libraries)), sorted(set(binaries))


def _policy(root: Path, profile: str = 'python_pure_v1') -> str:
    libraries, binaries = _runtime_paths(profile)
    q = lambda value: json.dumps(str(value), ensure_ascii=True)
    reads = [f"(subpath {q(path)})" for path in [str(root.resolve()), "/usr/lib", "/System", *libraries]]
    reads += [f"(literal {q(path)})" for path in [*binaries, "/", "/dev/null", "/dev/random", "/dev/urandom", "/private/var/select/sh"]]
    execs = " ".join(f"(literal {q(path)})" for path in binaries if path != SEATBELT)
    forks = "(deny process-fork)\n" if profile != 'posix_numeric_stream_v1' else ''
    return ("(version 1)\n(deny default)\n(allow process*)\n"
            f"{forks}"
            f"(deny process-exec* (require-not (require-any {execs})))\n"
            "(allow sysctl-read)\n(allow file-read-metadata)\n"
            f"(allow file-read* {' '.join(reads)})\n"
            f"(allow file-map-executable {' '.join(reads[1:])})\n"
            "(deny file-write*)\n(deny network*)\n(deny mach-lookup)\n(deny signal)\n")


def _cancelled(cancel: Any) -> bool:
    if cancel is None: return False
    return bool(cancel.is_set()) if hasattr(cancel, "is_set") else bool(cancel()) if callable(cancel) else bool(cancel)


def _cleanup_error(cleanup: dict, stage: str, error: BaseException) -> None:
    if cleanup['cleanup_error'] is None: cleanup['cleanup_error']=[]
    cleanup['cleanup_error'].append({'stage':stage,'type':type(error).__name__,
                                     'message':str(error)[:1024]})


def _cleanup_confirmed(cleanup: Any) -> bool:
    return (isinstance(cleanup,dict) and type(cleanup.get('group_signalled')) is bool
            and 'cleanup_error' in cleanup and cleanup.get('leader_reaped') is True
            and cleanup.get('group_absence_confirmed') is True
            and cleanup.get('cleanup_error') is None
            and cleanup.get('deadline_exceeded') is False)


def _kill_group(process: subprocess.Popen, timeout: float = .2, *,
                deadline: float | None = None) -> dict:
    """Signal only our new-session PGID, reap its leader, observe group absence.

    A normal killpg(...,0) return proves presence, never absence. This evidence
    concerns the owned PGID only; it does not track descendants that changed it.
    """
    end=min(time.monotonic()+max(0,timeout),deadline) if deadline is not None else time.monotonic()+max(0,timeout)
    cleanup={'group_signalled':False,'leader_reaped':False,
             'group_absence_confirmed':False,'cleanup_error':None,
             'deadline_exceeded':False,'child_id':process.pid}
    try:
        os.killpg(process.pid,signal.SIGKILL)
        cleanup['group_signalled']=True
    except ProcessLookupError:
        pass
    except OSError as error:
        _cleanup_error(cleanup,'group_signal',error)
    try:
        process.wait(timeout=max(0,end-time.monotonic()))
        cleanup['leader_reaped']=True
    except (OSError,subprocess.TimeoutExpired) as error:
        _cleanup_error(cleanup,'leader_wait',error)
    while time.monotonic() < end:
        try: os.killpg(process.pid,0)
        except ProcessLookupError:
            cleanup['group_absence_confirmed']=True
            break
        except OSError as error:
            _cleanup_error(cleanup,'group_probe',error)
            break
        time.sleep(min(.001,max(0,end-time.monotonic())))
    cleanup['deadline_exceeded']=time.monotonic() >= end
    return cleanup


def _available_bytes(fd: int) -> int:
    return struct.unpack('I',fcntl.ioctl(fd,termios.FIONREAD,struct.pack('I',0)))[0]


def _pipe_closed(fd: int) -> bool:
    if hasattr(select,'poll'):
        poller=select.poll()
        poller.register(fd,select.POLLIN|select.POLLHUP|select.POLLERR)
        return any(flags & select.POLLHUP for _,flags in poller.poll(0))
    if hasattr(select,'kqueue'):
        with select.kqueue() as queue:
            event=select.kevent(fd,filter=select.KQ_FILTER_READ,
                               flags=select.KQ_EV_ADD|select.KQ_EV_ENABLE)
            return any(item.flags & select.KQ_EV_EOF for item in queue.control([event],1,0))
    raise OSError('closed-pipe observation is unavailable')


def _spawn(root: Path, policy: Path, command: list[str], payload: bytes,
           timeout_ms: float, output_limit: int, cancel: Any,
           before_launch: Any = None, *, before_output: Any = None,
           after_output: Any = None, deadline: float | None = None,
           cleanup_reserve_ms: float = 50, protocol: _BatchProtocol | None = None) -> dict:
    limits = {"RLIMIT_CPU": 1, "RLIMIT_FSIZE": 0,
              "RLIMIT_CORE": 0, "RLIMIT_NOFILE": 64, "RLIMIT_NPROC": 1024}
    args = ['/bin/sh','-c',_RESOURCE_BOOTSTRAP,'vera-resource-bootstrap',
            SEATBELT, '-f', str(policy), *command]
    environment = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "LANG": "C",
                   "HOME": str(root), "TMPDIR": str(root), "PYTHONDONTWRITEBYTECODE": "1"}
    started = time.monotonic()
    child_deadline = started + timeout_ms/1000
    product_deadline = deadline if deadline is not None else started+MAX_CALL_MS/1000
    execution_deadline = min(child_deadline,product_deadline)-cleanup_reserve_ms/1000
    stopped = lambda status: {'status':status,'stdout':'','stderr':'','output_bytes':0,
                             'output_reserved_bytes':0,'launches':0,'child_id':None,
                             'process_group_reaped':False,'trace':[]}
    if _cancelled(cancel): return stopped('INTERRUPTED')
    if time.monotonic() >= execution_deadline: return stopped('REQUEST_TIMEOUT')
    selector=None
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    total=reserved=peak_resident=0
    trace=[]
    status='EXECUTED'
    primary_error=None
    propagate_error=False
    hook_error=None
    cleanup={'group_signalled':False,'leader_reaped':False,
             'group_absence_confirmed':False,'cleanup_error':None,
             'deadline_exceeded':False,'child_id':None}
    if before_launch is not None: before_launch()
    try:
        process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, cwd=root, env=environment,
                                   start_new_session=True, close_fds=True)
    except OSError as error:
        return dict(stopped('SANDBOX_UNAVAILABLE'),reason=str(error),launches=1,
                    process_group_reaped=False,cleanup=dict(cleanup,launch_failed=True))
    try:
        trace.append({'event':'child_started','child_id':process.pid})
        cleanup['child_id']=process.pid
        selector = selectors.DefaultSelector()
        for name in buffers:
            stream = getattr(process, name)
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        os.set_blocking(process.stdin.fileno(), False)
        selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
        pending = memoryview(payload)
        while selector.get_map():
            if _cancelled(cancel): status = "INTERRUPTED"; break
            if time.monotonic() >= execution_deadline:
                status = 'REQUEST_TIMEOUT' if product_deadline <= child_deadline else 'CHILD_TIMEOUT'
                break
            if process.poll() is None:
                try: resident, process_count = _resident_tree(process.pid)
                except (OSError, AttributeError): status = 'RESOURCE_MONITOR_UNAVAILABLE'; break
                peak_resident = max(peak_resident, resident)
                if resident > _MEMORY_LIMIT: status = 'MEMORY_LIMIT'; break
                if process_count > 32: status = 'PROCESS_LIMIT'; break
            for key, mask in selector.select(min(.005, max(0, execution_deadline - time.monotonic()))):
                if key.data == "stdin":
                    try:
                        count = os.write(key.fileobj.fileno(), pending) if pending else 0
                        pending = pending[count:]
                    except BrokenPipeError: pending = memoryview(b"")
                    if not pending:
                        selector.unregister(key.fileobj)
                        if protocol is None: key.fileobj.close()
                else:
                    try: available = _available_bytes(key.fileobj.fileno())
                    except OSError: status='OUTPUT_ACCOUNTING_UNAVAILABLE'; break
                    if available == 0:
                        try: closed=_pipe_closed(key.fileobj.fileno())
                        except OSError: status='OUTPUT_ACCOUNTING_UNAVAILABLE';break
                        if closed: selector.unregister(key.fileobj)
                        # No read/charge: a writer can write after FIONREAD=0.
                        # EOF is consumed as a closed-pipe state, not a 1-byte
                        # read reservation that would reject an exact cap.
                        continue
                    planned = min(available,65536,max(1,output_limit-total+1))
                    if before_output is not None:
                        try: before_output(planned,process.pid)
                        except BaseException as error:
                            hook_error=error
                            raise
                    reserved += planned
                    try: chunk = os.read(key.fileobj.fileno(),planned)
                    except BlockingIOError: continue
                    total += len(chunk)
                    if after_output is not None:
                        try: after_output(len(chunk),process.pid)
                        except BaseException as error:
                            hook_error=error
                            raise
                    if not chunk: selector.unregister(key.fileobj); continue
                    if total > output_limit: status = "OUTPUT_LIMIT"; break
                    buffers[key.data].extend(chunk)
                    if protocol is not None and key.data == 'stdout':
                        try: permits = protocol.feed(chunk)
                        except _ProtocolError as error:
                            status='RUNNER_PROTOCOL_ERROR'
                            trace.append({'event':'protocol_error','reason':str(error)})
                            break
                        if permits:
                            pending = memoryview(bytes(pending)+permits)
                            if process.stdin.closed:
                                status='RUNNER_PROTOCOL_ERROR';break
                            if process.stdin not in [item.fileobj for item in selector.get_map().values()]:
                                selector.register(process.stdin,selectors.EVENT_WRITE,'stdin')
            if status != "EXECUTED": break
        # Kill the entire session even when its leader exited: descendants may
        # retain pipe handles or keep running after the artifact returned.
        if status == 'EXECUTED':
            if protocol is not None:
                try: protocol.complete()
                except _ProtocolError as error:
                    status='RUNNER_PROTOCOL_ERROR'
                    trace.append({'event':'protocol_error','reason':str(error)})
            try: process.wait(timeout=min(.005, max(.001, execution_deadline-time.monotonic())))
            except subprocess.TimeoutExpired: pass
    except (OSError,ValueError,KeyError,RuntimeError) as error:
        primary_error=error
        propagate_error=(error is hook_error or (protocol is not None and error is protocol.hook_error))
        status='SANDBOX_UNAVAILABLE'
        trace.append({'event':'environment_error','type':type(error).__name__,'reason':str(error)[:1024]})
    except BaseException as error:
        primary_error=error
        propagate_error=True
    finally:
        try:
            cleanup=_kill_group(process,.2,deadline=product_deadline)
            if not isinstance(cleanup,dict): raise TypeError('cleanup must return an evidence dictionary')
        except BaseException as error:
            cleanup={'group_signalled':False,'leader_reaped':False,
                     'group_absence_confirmed':False,'cleanup_error':None,
                     'deadline_exceeded':time.monotonic() >= product_deadline,'child_id':process.pid}
            _cleanup_error(cleanup,'group_cleanup',error)
        if selector is not None:
            try: selector.close()
            except BaseException as error: _cleanup_error(cleanup,'selector_close',error)
        for name in ('stdin','stdout','stderr'):
            try:
                stream=getattr(process,name)
                if stream is not None and not stream.closed: stream.close()
            except BaseException as error: _cleanup_error(cleanup,'close_'+name,error)
        cleanup.update(output_bytes=total,output_reserved_bytes=reserved,launches=1)
        cleanup.update(child_deadline_exceeded=time.monotonic() >= child_deadline,
                       child_elapsed_ms=(time.monotonic()-started)*1000,
                       child_limit_ms=timeout_ms,cleanup_reserve_ms=cleanup_reserve_ms)
        if time.monotonic() >= product_deadline: cleanup['deadline_exceeded']=True
    reaped=_cleanup_confirmed(cleanup)
    if primary_error is not None and propagate_error:
        details=getattr(primary_error,'details',None)
        if isinstance(primary_error,ContractError) and not isinstance(details,dict):
            details={'original_details':details}
            primary_error.details=details
        if isinstance(details,dict):
            details['cleanup']=cleanup
            details['child_attempt']={'launches':1,'child_id':process.pid,'output_bytes':total,
                                      'output_reserved_bytes':reserved,'trace':trace,
                                      'cases':protocol.stats() if protocol is not None else None}
        if not reaped and hasattr(primary_error,'add_note'):
            primary_error.add_note('sandbox cleanup is unconfirmed: '+json.dumps(cleanup,separators=(',',':')))
        raise primary_error
    stdout, stderr = (bytes(buffers[name]).decode("utf-8", errors="replace") for name in ("stdout", "stderr"))
    if status == "EXECUTED" and process.returncode:
        status = "RESOURCE_LIMIT_UNAVAILABLE" if "RESOURCE_LIMIT_UNAVAILABLE" in stderr else "PROCESS_ERROR"
    if status == 'EXECUTED' and cleanup['child_deadline_exceeded']: status='CHILD_TIMEOUT'
    prior_status=status
    if not reaped: status='EXECUTION_INCOMPLETE'
    trace.append({'event':'child_stopped','child_id':process.pid,'status':status,'reaped':reaped})
    response={"status": status, "stdout": stdout, "stderr": stderr,
            "exit_code": process.returncode, "output_bytes": total,
            "output_reserved_bytes":reserved,"child_id":process.pid,"trace":trace,"launches": 1,
            "elapsed_ms": 0.0,
            "limits": limits, "process_group_reaped": reaped,
            "cleanup":cleanup,"prior_status":prior_status,
            "memory": {"limit_bytes":_MEMORY_LIMIT,"peak_sampled_resident_bytes":peak_resident,
                       "enforcement":"5ms resident-tree watchdog; not an instantaneous hard cap",
                       "os_as_data_limit":"unavailable on tested macOS; not claimed"}}
    finished=time.monotonic()
    response['elapsed_ms']=(finished-started)*1000
    cleanup['child_elapsed_ms']=response['elapsed_ms']
    cleanup['child_deadline_exceeded']=finished >= child_deadline
    if response['status']=='EXECUTED' and cleanup['child_deadline_exceeded']:
        response['status']='CHILD_TIMEOUT'
        trace[-1]['status']='CHILD_TIMEOUT'
    return response


def run_artifact(profile: str, source: str, interface: dict, cases: list[dict], *,
                 timeout_ms: int = MAX_CHILD_MS, output_limit: int = MAX_OUTPUT_BYTES,
                 cancel: Any = None, before_launch: Any = None,
                 before_case: Any = None, before_output: Any = None,
                 after_output: Any = None, deadline: float | None = None,
                 cleanup_reserve_ms: float = 50) -> dict:
    """Run up to 12 independent witnesses and return unrepaired observations.

    interface = {name, parameters:[str], keyword_only:[str], columns:[str],
                 ordered:bool, argv:[str]}.
    Python/Node cases use args/kwargs; SQL uses tables:{name:{schema:[{name,
    type:INTEGER|REAL|TEXT, nullable:bool}],rows:[[...]]}}; shell uses stdin/argv.
    Case metadata is never an expected value and does not affect decoding.
    status EXECUTED means execution completed, not that a contract was met.
    A capability probe is a counted launch; no unsafe fallback or retry exists.
    Budget hooks run immediately before each launch/logical witness attempt;
    their exceptions propagate through cleanup without being reclassified.
    before_output(planned_bytes,child_pid) reserves a FIONREAD-bounded read;
    after_output(actual_bytes,child_pid) observes its actual byte cost. EOF
    uses poll HUP or kqueue EOF, consumes no bytes and needs no speculative read.
    deadline is absolute monotonic product time, separate from user cancel.
    Python/SQL use one batch child; Node uses fresh processes. Shell is held.
    process_group_reaped is a compatibility alias for leader reap AND owned
    PGID absence, no cleanup errors, and no cleanup deadline overrun. It is
    never evidence of tracking descendants that moved to another group.
    """
    started = time.monotonic()
    if deadline is not None and (type(deadline) not in (int,float) or not math.isfinite(deadline)):
        return _reason(profile,source,'INPUT_UNSUPPORTED','deadline must be finite monotonic seconds')
    if type(cleanup_reserve_ms) not in (int,float) or not 0 <= cleanup_reserve_ms <= MAX_CHILD_MS:
        return _reason(profile,source,'INPUT_UNSUPPORTED','cleanup reserve must be in [0,200] ms')
    product_deadline=min(started+MAX_CALL_MS/1000,deadline) if deadline is not None else started+MAX_CALL_MS/1000
    try: issue = _validate(profile, source, interface, cases)
    except (TypeError, ValueError, RecursionError): issue = "malformed interface/case data"
    if issue: return _reason(profile, source, "INPUT_UNSUPPORTED", issue)
    if not isinstance(timeout_ms, (int, float)) or isinstance(timeout_ms, bool) or not 0 < timeout_ms <= MAX_CHILD_MS:
        return _reason(profile, source, "INPUT_UNSUPPORTED", "child timeout must be in (0,200] ms")
    if type(output_limit) is not int or not 0 <= output_limit <= MAX_OUTPUT_BYTES:
        return _reason(profile, source, "INPUT_UNSUPPORTED", "output byte limit must be in [0,1048576]")
    issue = _source_gate(profile, source)
    if issue: return _reason(profile, source, "UNSAFE_OR_UNSUPPORTED_ARTIFACT", issue)
    if profile == 'posix_numeric_stream_v1':
        refused=_reason(profile,source,'DESCENDANT_ISOLATION_UNVERIFIED',
                        'fork-capable shell descendants outside the owned PGID are not accounted for')
        refused['code']=None
        return refused
    if sys.platform != "darwin" or not all(Path(path).is_file() for path in (PYTHON, SEATBELT)):
        return _reason(profile, source, "SANDBOX_UNAVAILABLE", "required macOS Seatbelt/Python runtime is unavailable")
    if profile == "node_commonjs_sync_v1" and not Path(NODE).is_file():
        return _reason(profile, source, "SANDBOX_UNAVAILABLE", "fixed Node runtime is unavailable")
    if _cancelled(cancel): return _reason(profile, source, "INTERRUPTED", "user cancelled before any launch")
    if time.monotonic() >= product_deadline-cleanup_reserve_ms/1000:
        return _reason(profile,source,'REQUEST_TIMEOUT','product deadline has no execution/cleanup time left')
    if not _LOCK.acquire(blocking=False): return _reason(profile, source, "SANDBOX_BUSY", "one artifact execution is already active")
    result = _reason(profile, source, "EXECUTED", "finite observations only")
    result['development_revision']='r3'
    def record_child(child):
        result['stats']['launches'] += child['launches']
        result['stats']['output_bytes'] += child['output_bytes']
        result['stats']['output_reserved_bytes'] += child.get('output_reserved_bytes',0)
        result['stats']['children'].append({'child_id':child.get('child_id'),'status':child['status'],
                                           'output_bytes':child['output_bytes'],
                                           'output_reserved_bytes':child.get('output_reserved_bytes',0),
                                           'cleanup':child.get('cleanup')})
        result['trace'].extend(child.get('trace',[]))
    extensions={'before_output':before_output,'after_output':after_output,
                'deadline':product_deadline,'cleanup_reserve_ms':cleanup_reserve_ms}
    try:
        with tempfile.TemporaryDirectory(prefix="vera-contract-") as directory, tempfile.TemporaryDirectory(prefix="vera-probe-") as probe_directory:
            root = Path(directory)
            policy = root / "policy.sb"
            policy.write_text(_policy(root,profile), encoding="utf-8")
            probe_path = root / "probe.py"
            probe_path.write_text(_PROBE, encoding="utf-8")
            secret = Path(probe_directory) / "read-sentinel"
            secret.write_text("Vera sandbox boundary sentinel", encoding="utf-8")
            probe_payload = json.dumps({"read": str(secret), "write": str(Path(probe_directory) / "must-not-exist"), "local": str(root / "must-not-exist")}).encode()
            remaining = lambda: max(0.0,(product_deadline-time.monotonic())*1000)
            probe = _spawn(root, policy, [_python_binary(),"-I","-S",str(probe_path)], probe_payload,
                           min(timeout_ms,remaining()), output_limit, cancel, before_launch,**extensions)
            record_child(probe)
            try: proof = json.loads(probe['stdout']) if probe['status'] == 'EXECUTED' else {}
            except (ValueError, TypeError): proof = {}
            boundaries = ('external_read','external_write','local_write','network','unlisted_exec','fork_denied')
            if not (proof.get('verified') is True and isinstance(proof.get('checks'),dict)
                    and all(proof['checks'].get(boundary) is True for boundary in boundaries)
                    and _cleanup_confirmed(probe.get('cleanup'))):
                result.update(status=probe['status'] if probe['status'] in ('INTERRUPTED','REQUEST_TIMEOUT','EXECUTION_INCOMPLETE') else 'SANDBOX_UNAVAILABLE',
                              reason='OS isolation probe did not establish every boundary', probe=probe)
                return result
            result['isolation'].update(verified=True, checks=proof['checks'], limits=probe['limits'],
                                       metadata_reads='filesystem metadata is readable; external file data is denied',
                                       runtime_reads='OS libraries and fixed Homebrew runtime libraries only',
                                       memory=probe['memory'],
                                       descendant_scope='owned new-session PGID; process-fork denial observed by trusted probe',
                                       fork_denied=True,probe_cleanup=probe['cleanup'])
            artifact = root / {'python_pure_v1':'artifact.py','node_commonjs_sync_v1':'artifact.cjs','sqlite_select_v1':'artifact.sql','posix_numeric_stream_v1':'artifact.sh'}[profile]
            artifact.write_text(source, encoding='utf-8')
            runner = root / ('runner.cjs' if profile == 'node_commonjs_sync_v1' else 'runner.py')
            if profile != 'posix_numeric_stream_v1': runner.write_text({'python_pure_v1':_PY_RUNNER,'node_commonjs_sync_v1':_NODE_RUNNER,'sqlite_select_v1':_SQL_RUNNER}[profile],encoding='utf-8')
            if profile in ('python_pure_v1','sqlite_select_v1'):
                runner.write_text(_batch_program(profile),encoding='utf8')
                protocol=_BatchProtocol(len(cases),before_case)
                payload=json.dumps({'cases':cases,'interface':interface,'output_limit':output_limit},
                                   ensure_ascii=False,allow_nan=False).encode('utf8')+b'\n'
                child=_spawn(root,policy,[_python_binary(),'-I','-S',str(runner),str(artifact)],
                             payload,min(timeout_ms,remaining()),output_limit,cancel,before_launch,
                             protocol=protocol,**extensions)
                record_child(child)
                result['stats'].update(protocol.stats(),batch=True)
                result['trace'].extend(protocol.trace)
                result['results']=protocol.results
                for entry in result['results']:
                    entry['process_stderr']=child['stderr']
                    entry['process_stderr_scope']='whole_batch'
                    entry['stderr']=entry.get('stderr','')+child['stderr']
                    entry['exit_code']=child.get('exit_code')
                    entry['process_group_reaped']=child.get('process_group_reaped',False)
                    entry['cleanup']=child.get('cleanup')
                failures=[entry for entry in result['results'] if entry['status']!='EXECUTED']
                if child['status']!='EXECUTED':
                    result.update(status=child['status'],reason='batch child did not complete',batch_stop=child)
                elif failures:
                    result.update(status=failures[0]['status'],reason='a batch witness failed')
                elif not (protocol.done and protocol.reserved==protocol.attempted==protocol.finished==len(cases)):
                    result.update(status='EXECUTION_INCOMPLETE',reason='batch did not finish all permitted witnesses')
                elif remaining() <= 0:
                    result.update(status='REQUEST_TIMEOUT',reason='product deadline expired before returning batch')
                return result
            for index, case in enumerate(cases):
                if _cancelled(cancel): result.update(status='INTERRUPTED',reason='user cancelled before next witness'); break
                if remaining() <= cleanup_reserve_ms: result.update(status='REQUEST_TIMEOUT',reason='product execution/cleanup deadline exhausted'); break
                if profile == 'posix_numeric_stream_v1':
                    command = ['/bin/sh',str(artifact),*case.get('argv',[])]
                    payload = case.get('stdin','').encode('utf-8')
                else:
                    command = ([NODE,'--no-warnings','--max-old-space-size=64','--stack-size=512',str(runner),str(artifact)] if profile=='node_commonjs_sync_v1'
                               else [_python_binary(),'-I','-S',str(runner),str(artifact)])
                    payload=json.dumps({'case':case,'interface':interface,'timeout_ms':max(1,int(min(timeout_ms,remaining()))),'output_limit':output_limit},ensure_ascii=False,allow_nan=False).encode('utf-8')
                if before_case is not None: before_case()
                result['stats']['cases_reserved'] += 1
                observation = _spawn(root, policy, command, payload, min(timeout_ms,remaining()), output_limit, cancel, before_launch,**extensions)
                record_child(observation)
                if profile=='posix_numeric_stream_v1':
                    entry = dict(observation)
                    entry['protocol'] = {'stdin':case.get('stdin',''),'argv':case.get('argv',[]),'requested_argv':interface.get('argv',[])}
                    entry['mutation'] = {'unchanged':True,'enforced':'seatbelt_no_file_write'}
                elif observation['status']=='EXECUTED':
                    try:
                        entry = json.loads(observation['stdout'])
                        if not isinstance(entry,dict) or 'status' not in entry: raise ValueError('invalid runner result')
                        entry['process_stderr'] = observation['stderr']
                        entry['stderr'] = entry.get('stderr','') + observation['stderr']
                        entry['exit_code'] = observation['exit_code']
                        entry['process_group_reaped'] = observation['process_group_reaped']
                        entry['cleanup'] = observation.get('cleanup')
                    except (ValueError, TypeError): entry=dict(observation,status='RUNNER_PROTOCOL_ERROR')
                else: entry=dict(observation)
                entry['index']=index
                result['results'].append(entry)
                # Fresh-process profiles have a completed-call observation,
                # not a startup marker. A timed-out launch stays unconfirmed.
                if observation['status']=='EXECUTED':
                    result['stats']['cases_attempted'] += 1
                    result['stats']['cases_finished'] += 1
                result['stats']['cases']=result['stats']['cases_attempted']
                result['stats']['unconfirmed_starts']=result['stats']['cases_reserved']-result['stats']['cases_attempted']
                if entry['status'] != 'EXECUTED':
                    result.update(status=entry['status'],reason='witness did not complete normally'); break
            if result['status']=='EXECUTED' and len(result['results']) != len(cases):
                result.update(status='EXECUTION_INCOMPLETE',reason='not every requested witness was executed')
            if result['status']=='EXECUTED' and remaining() <= 0:
                result.update(status='REQUEST_TIMEOUT',reason='product deadline exhausted before returning observations')
            return result
    finally:
        result['stats']['elapsed_ms']=(time.monotonic()-started)*1000
        _LOCK.release()
