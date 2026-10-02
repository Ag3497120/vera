"""Self fixtures only: no sealed/heldout/development-80 content.

Unit tests prove fail-closed plumbing and profile gates.  Opt-in integration
tests require actual Seatbelt execution under the unchanged 200 ms child cap:
VERA_SANDBOX_INTEGRATION=1 python3.11 -m unittest tests/test_contract_sandbox.py
Do not report skipped integration tests as verified artifact behavior.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from verantyx import contract_sandbox as sandbox


class SandboxBoundaryTests(unittest.TestCase):
    def call(self, source='def measure(items):\n    return len(items)', cases=None, **kwargs):
        return sandbox.run_artifact('python_pure_v1', source,
                                    {'name':'measure','parameters':['items']},
                                    [{'args':[[]]}] if cases is None else cases, **kwargs)

    def test_unknown_profile_never_launches(self):
        with patch.object(sandbox, '_spawn') as spawn:
            result=sandbox.run_artifact('unregistered','x',{},[{}])
        self.assertEqual(result['status'],'INPUT_UNSUPPORTED')
        spawn.assert_not_called()

    def test_empty_witnesses_are_not_success(self):
        self.assertEqual(self.call(cases=[])['status'],'INPUT_UNSUPPORTED')

    def test_artifact_size_boundary_is_bytes(self):
        source='def measure(items):\n    return 0\n#'
        source+='x'*(sandbox.MAX_SOURCE_BYTES-len(source.encode()))
        self.assertIsNone(sandbox._validate('python_pure_v1',source,{'name':'measure','parameters':['items']},[{'args':[[]]}]))
        self.assertIsNotNone(sandbox._validate('python_pure_v1',source+'あ',{'name':'measure','parameters':['items']},[{'args':[[]]}]))

    def test_limits_cannot_be_increased(self):
        with patch.object(sandbox,'_spawn') as spawn:
            self.assertEqual(self.call(timeout_ms=201)['status'],'INPUT_UNSUPPORTED')
            self.assertEqual(self.call(output_limit=1048577)['status'],'INPUT_UNSUPPORTED')
            self.assertEqual(self.call(timeout_ms=0)['status'],'INPUT_UNSUPPORTED')
        spawn.assert_not_called()

    def test_case_count_boundary(self):
        interface={'name':'measure','parameters':['items']}
        self.assertIsNone(sandbox._validate('python_pure_v1','x',interface,[{}]*12))
        self.assertIsNotNone(sandbox._validate('python_pure_v1','x',interface,[{}]*13))

    def test_collection_size_and_flat_record_boundaries(self):
        interface={'name':'measure','parameters':['items']}
        self.assertIsNone(sandbox._validate('python_pure_v1','x',interface,[{'args':[[0]*32]}]))
        self.assertIsNotNone(sandbox._validate('python_pure_v1','x',interface,[{'args':[[0]*33]}]))
        self.assertIsNotNone(sandbox._validate('python_pure_v1','x',interface,[{'args':[[{'value':[1]}]]}]))

    def test_invalid_utf8_source_has_typed_refusal(self):
        with patch.object(sandbox,'_spawn') as spawn:
            result=self.call('\ud800')
        self.assertEqual(result['status'],'INPUT_UNSUPPORTED')
        self.assertIsNone(result['artifact_sha256'])
        spawn.assert_not_called()

    def test_keyword_only_is_parameter_subset(self):
        self.assertIsNone(sandbox._validate('python_pure_v1','x',{'name':'measure','parameters':['items','cutoff'],'keyword_only':['cutoff']},[{}]))
        self.assertIsNotNone(sandbox._validate('python_pure_v1','x',{'name':'measure','parameters':['items'],'keyword_only':['cutoff']},[{}]))

    def test_explicit_cancel_has_zero_launches(self):
        event=threading.Event();event.set()
        with patch.object(sandbox,'_spawn') as spawn:
            result=self.call(cancel=event)
        self.assertEqual(result['status'],'INTERRUPTED')
        self.assertEqual(result['stats']['cases'],0)
        spawn.assert_not_called()

    def test_no_unsafe_fallback_after_probe_failure(self):
        failed={'status':'PROCESS_ERROR','stdout':'','stderr':'sandbox_apply EPERM',
                'launches':1,'output_bytes':0,'exit_code':71}
        with patch.object(sandbox,'_spawn',return_value=failed) as spawn:
            result=self.call()
        self.assertEqual(result['status'],'SANDBOX_UNAVAILABLE')
        self.assertEqual(result['results'],[])
        self.assertFalse(result['isolation']['verified'])
        self.assertEqual(spawn.call_count,1)
        self.assertEqual(result['stats']['cases'],0)

    def test_probe_must_confirm_every_boundary(self):
        fake={'status':'EXECUTED','stdout':json.dumps({'verified':False,'checks':{'network':False}}),
              'stderr':'','launches':1,'output_bytes':40,'exit_code':0}
        with patch.object(sandbox,'_spawn',return_value=fake) as spawn:
            result=self.call()
        self.assertEqual(result['status'],'SANDBOX_UNAVAILABLE')
        self.assertEqual(spawn.call_count,1)

    def test_probe_verified_flag_does_not_override_failed_boundary(self):
        fake={'status':'EXECUTED','stdout':json.dumps({'verified':True,'checks':{'network':False}}),
              'stderr':'','launches':1,'output_bytes':40,'exit_code':0}
        with patch.object(sandbox,'_spawn',return_value=fake) as spawn:
            result=self.call()
        self.assertEqual(result['status'],'SANDBOX_UNAVAILABLE')
        self.assertEqual(spawn.call_count,1)

    def test_launch_hook_runs_before_failed_popen_attempt(self):
        events=[]
        def popen(*args,**kwargs):
            self.assertEqual(events,['launch'])
            raise OSError('synthetic launch failure')
        with tempfile.TemporaryDirectory() as d, patch.object(sandbox.subprocess,'Popen',side_effect=popen):
            result=sandbox._spawn(Path(d),Path(d)/'unused',[],b'',200,1048576,None,
                                  before_launch=lambda:events.append('launch'))
        self.assertEqual(result['launches'],1)
        self.assertEqual(result['status'],'SANDBOX_UNAVAILABLE')

    def test_budget_hook_exception_releases_lock_and_temp_paths(self):
        events=[];roots=[]
        checks={name:True for name in ('external_read','external_write','local_write','network','unlisted_exec','fork_denied')}
        def probe(root,policy,command,payload,timeout,limit,cancel,before_launch,**options):
            roots.append(root)
            before_launch()
            if 'protocol' in options:
                options['protocol'].feed(b'{"event":"ready","index":0}\n')
            return {'status':'EXECUTED','stdout':json.dumps({'verified':True,'checks':checks}),
                    'stderr':'','launches':1,'output_bytes':80,'exit_code':0,'limits':{},'memory':{},
                    'cleanup':{'group_signalled':True,'leader_reaped':True,'group_absence_confirmed':True,
                               'cleanup_error':None,'deadline_exceeded':False}}
        class BudgetStop(Exception): pass
        def case_hook():
            events.append('case')
            raise BudgetStop('synthetic witness budget')
        with patch.object(sandbox,'_spawn',side_effect=probe):
            with self.assertRaises(BudgetStop):
                self.call(before_launch=lambda:events.append('launch'),before_case=case_hook)
        self.assertEqual(events,['launch','launch','case'])
        self.assertFalse(any(root.exists() for root in roots))
        self.assertTrue(sandbox._LOCK.acquire(blocking=False))
        sandbox._LOCK.release()

    def test_nonfinite_case_is_rejected(self):
        self.assertEqual(self.call(cases=[{'args':[[float('inf')]]}])['status'],'INPUT_UNSUPPORTED')

    def test_pure_python_gate_rejects_capabilities(self):
        for source in ('import os\ndef measure(items): return os.getcwd()',
                       'def measure(items): return open("/etc/passwd").read()',
                       'def measure(items): return ().__class__.__bases__',
                       'def measure(items): return eval("1")'):
            with self.subTest(source=source), patch.object(sandbox,'_spawn') as spawn:
                self.assertEqual(self.call(source)['status'],'UNSAFE_OR_UNSUPPORTED_ARTIFACT')
                spawn.assert_not_called()

    def test_pure_fragment_allows_composition(self):
        source='def inner(items):\n    return sorted(set(items))\ndef measure(items):\n    return sum([abs(x)*2 for x in inner(items)])'
        self.assertIsNone(sandbox._source_gate('python_pure_v1',source))
        self.assertIsNone(sandbox._source_gate('node_commonjs_sync_v1','module.exports.measure = function(items) { return Array.from(new Set(items)).map(x => Math.abs(x)); };'))

    def test_shell_gates_background_and_external_exec(self):
        for source in ('/usr/bin/awk \'{print $1}\' &',
                       '/usr/bin/awk \'{print $1}\' > /tmp/out',
                       '/usr/bin/awk \'BEGIN {system("/bin/sh")}\'',
                       '/usr/bin/awk \'{print $1}\'\n/bin/sh -c true'):
            self.assertIsNotNone(sandbox._source_gate('posix_numeric_stream_v1',source))
        self.assertIsNone(sandbox._source_gate('posix_numeric_stream_v1','#!/bin/sh\n/usr/bin/awk \'{s += $1} END {print s+0}\''))
        self.assertIsNone(sandbox._source_gate('posix_numeric_stream_v1','LC_ALL=C /usr/bin/awk \'{print $1}\''))

    def test_shell_protocol_preserves_exact_bytes(self):
        profile='posix_numeric_stream_v1'
        self.assertIsNone(sandbox._validate(profile,'x',{},[{'stdin':'0\n-2\n','argv':['3']}]))
        for stdin in ('0','+1\n','01\n','-0\n','1\n\n'):
            self.assertIsNotNone(sandbox._validate(profile,'x',{},[{'stdin':stdin}]))

    def test_sql_input_types_and_schema(self):
        table={'schema':[{'name':'value','type':'INTEGER','nullable':False}], 'rows':[[1]]}
        self.assertIsNone(sandbox._validate('sqlite_select_v1','SELECT value FROM items',{'columns':['value']},[{'tables':{'items':table}}]))
        for value in (True,None,'1',1.0):
            table['rows']=[[value]]
            self.assertIsNotNone(sandbox._validate('sqlite_select_v1','x',{},[{'tables':{'items':table}}]))

    def test_policy_has_no_home_data_or_write_allowance(self):
        with tempfile.TemporaryDirectory() as d:
            policy=sandbox._policy(Path(d))
        self.assertIn('(deny default)',policy)
        self.assertIn('(deny network*)',policy)
        self.assertIn('(deny file-write*)',policy)
        self.assertIn('(deny process-exec*',policy)
        self.assertNotIn('(subpath "/Users")',policy)
        self.assertNotIn('(subpath "/private/var")',policy)

    def test_result_is_json_and_carries_exact_artifact_hash(self):
        source='def measure(items): return len(items)'
        result=self.call(source,cases=[])
        self.assertEqual(result['artifact_sha256'],hashlib.sha256(source.encode()).hexdigest())
        json.dumps(result,allow_nan=False)
        self.assertNotIn('passed',result)
        self.assertEqual(result['correctness'],'not_established_by_execution')


@unittest.skipUnless(os.environ.get('VERA_SANDBOX_INTEGRATION')=='1','requires opt-in actual OS execution; skipped is not verification')
class ActualSeatbeltTests(unittest.TestCase):
    def require(self,result):
        self.assertEqual(result['status'],'EXECUTED',json.dumps(result,ensure_ascii=False))
        self.assertTrue(result['isolation']['verified'])
        self.assertTrue(all(result['isolation']['checks'].values()))
        return result['results']

    def test_python_empty_boundary_keyword_only_and_reset(self):
        source='counter=0\ndef scale(items, *, factor):\n    global counter\n    counter += 1\n    return [x*factor+counter for x in items]'
        result=sandbox.run_artifact('python_pure_v1',source,{'name':'scale','parameters':['items','factor'],'keyword_only':['factor']},
                                    [{'args':[[]],'kwargs':{'factor':2}},{'args':[[0,-1,2]],'kwargs':{'factor':2}},{'args':[[0]],'kwargs':{'factor':2}}])
        rows=self.require(result)
        self.assertEqual([row['value'] for row in rows],[[],[1,-1,5],[1]])
        self.assertTrue(all(row['signature_matches'] and row['mutation']['unchanged'] for row in rows))

    def test_python_signature_and_type_mutation_are_not_repaired(self):
        result=sandbox.run_artifact('python_pure_v1','def measure(items):\n    items[0]=True\n    return items',{'name':'measure','parameters':['items']},[{'args':[[1]]}])
        row=self.require(result)[0]
        self.assertFalse(row['mutation']['unchanged'])
        self.assertEqual(row['typed_value']['items'][0]['type'],'bool')
        wrong=sandbox.run_artifact('python_pure_v1','def measure(other): return other',{'name':'measure','parameters':['items']},[{'args':[[1]]}])
        self.assertFalse(self.require(wrong)[0]['signature_matches'])

    def test_node_export_undefined_and_reset(self):
        source='let counter=0; module.exports.scale=function(items) { counter++; return items.map(x=>x+counter); };'
        result=sandbox.run_artifact('node_commonjs_sync_v1',source,{'name':'scale','parameters':['items']},[{'args':[[0]]},{'args':[[0]]}])
        rows=self.require(result)
        self.assertEqual([row['value'] for row in rows],[[1],[1]])
        self.assertTrue(all(row['signature_matches'] for row in rows))
        result=sandbox.run_artifact('node_commonjs_sync_v1','module.exports.scale=function(items) {return {missing:undefined,explicit:null};}',{'name':'scale','parameters':['items']},[{'args':[[]]}])
        fields=self.require(result)[0]['typed_value']['fields']
        self.assertEqual(fields['missing']['type'],'undefined')
        self.assertEqual(fields['explicit']['type'],'null')

    def test_sql_column_alias_order_multiplicity_and_authorizer(self):
        case={'tables':{'items':{'schema':[{'name':'value','type':'INTEGER'}], 'rows':[[2],[1],[2]]}}}
        result=sandbox.run_artifact('sqlite_select_v1','SELECT value AS actual FROM items ORDER BY value',{'columns':['actual'],'ordered':True},[case])
        row=self.require(result)[0]
        self.assertEqual(row['columns'],['actual'])
        self.assertEqual(row['rows'],[[1],[2],[2]])
        self.assertEqual(row['row_types'],[['integer']]*3)
        result=sandbox.run_artifact('sqlite_select_v1','DELETE FROM items',{'columns':['actual']},[case])
        self.assertEqual(result['status'],'ARTIFACT_ERROR')

    def test_shell_protocol_exact_empty_and_argv(self):
        result=sandbox.run_artifact('posix_numeric_stream_v1','/usr/bin/awk -v k="$1" \'{print $1*k}\'',{'argv':['factor']},[{'stdin':'','argv':['2']},{'stdin':'0\n-2\n3\n','argv':['2']}])
        # The original protocol fixture remains; r3 does not certify its
        # fork-capable runtime until descendants outside its PGID are tracked.
        self.assertEqual(result['status'],'DESCENDANT_ISOLATION_UNVERIFIED')
        self.assertIsNone(result['code'])
        self.assertEqual(result['stats']['launches'],0)

    def test_child_timeout_and_output_limit_are_not_success(self):
        result=sandbox.run_artifact('python_pure_v1','def measure(items):\n    while True: pass',{'name':'measure','parameters':['items']},[{'args':[[]]}])
        self.assertEqual(result['status'],'CHILD_TIMEOUT')
        self.assertTrue(result['batch_stop']['process_group_reaped'])
        result=sandbox.run_artifact('python_pure_v1','def measure(items):\n    print("x"*2000000)\n    return 0',{'name':'measure','parameters':['items']},[{'args':[[]]}])
        self.assertEqual(result['status'],'OUTPUT_LIMIT')


if __name__=='__main__':
    unittest.main()
