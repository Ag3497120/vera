"""r2 batch/accounting self fixtures; default tests launch no subprocess.

The root's one-worker test invocation owns all execution. Actual OS tests stay
opt-in and preserve registered limits; skipped tests are not dynamic evidence.
"""
import ast
from contextlib import contextmanager
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from verantyx import contract_sandbox as sandbox


def frame(event,index=None,result=None):
    value={'event':event}
    if index is not None: value['index']=index
    if result is not None: value['result']=result
    return json.dumps(value).encode()+b'\n'


def cleanup_fixture(confirmed=True):
    return {'group_signalled':True,'leader_reaped':confirmed,
            'group_absence_confirmed':confirmed,'cleanup_error':None,
            'deadline_exceeded':False,'child_id':31337}


class BatchProtocolTests(unittest.TestCase):
    def test_per_case_charge_precedes_permit_and_start_is_separate(self):
        events=[]
        protocol=sandbox._BatchProtocol(2,lambda:events.append('charge'))
        self.assertEqual(protocol.feed(frame('ready',0)),b'{"permit": 0}\n')
        self.assertEqual(events,['charge'])
        self.assertEqual(protocol.stats()['cases_reserved'],1)
        self.assertEqual(protocol.stats()['cases_attempted'],0)
        protocol.feed(frame('started',0))
        protocol.feed(frame('result',0,{'status':'EXECUTED','value':[]}))
        protocol.feed(frame('ready',1))
        self.assertEqual(events,['charge','charge'])
        self.assertEqual(protocol.stats()['unconfirmed_starts'],1)
        protocol.feed(frame('started',1)+frame('result',1,{'status':'EXECUTED','value':[0]}))
        protocol.feed(frame('done',result={'finished':2}))
        protocol.complete()
        self.assertEqual(protocol.stats(),{'cases_reserved':2,'cases_attempted':2,'cases_finished':2,'cases':2,'unconfirmed_starts':0})

    def test_split_frames_do_not_charge_early(self):
        count=[];protocol=sandbox._BatchProtocol(1,lambda:count.append(1))
        message=frame('ready',0)
        self.assertEqual(protocol.feed(message[:-1]),b'')
        self.assertEqual(count,[])
        self.assertTrue(protocol.feed(message[-1:]))
        self.assertEqual(count,[1])

    def test_budget_rejection_issues_no_permit(self):
        class Stop(Exception): pass
        def reject(): raise Stop('witness budget')
        protocol=sandbox._BatchProtocol(1,reject)
        with self.assertRaises(Stop): protocol.feed(frame('ready',0))
        self.assertEqual(protocol.stats()['cases_reserved'],0)
        self.assertEqual(protocol.stats()['cases_attempted'],0)

    def test_duplicate_unpermitted_or_boolean_index_is_rejected(self):
        for invalid in (frame('started',0),frame('ready',1),frame('ready',False)):
            with self.subTest(invalid=invalid),self.assertRaises(sandbox._ProtocolError):
                sandbox._BatchProtocol(1).feed(invalid)
        protocol=sandbox._BatchProtocol(1)
        protocol.feed(frame('ready',0)+frame('started',0))
        with self.assertRaises(sandbox._ProtocolError): protocol.feed(frame('started',0))

    def test_failure_does_not_execute_later_cases_or_become_success(self):
        protocol=sandbox._BatchProtocol(2)
        protocol.feed(frame('ready',0)+frame('started',0))
        protocol.feed(frame('result',0,{'status':'ARTIFACT_ERROR','error':'independent fixture'}))
        with self.assertRaises(sandbox._ProtocolError): protocol.feed(frame('ready',1))
        protocol.feed(frame('done',result={'finished':1}))
        protocol.complete()
        self.assertEqual(protocol.results[0]['status'],'ARTIFACT_ERROR')
        self.assertEqual(protocol.stats()['cases_finished'],1)

    def test_incomplete_completion_is_not_success(self):
        protocol=sandbox._BatchProtocol(1)
        protocol.feed(frame('ready',0))
        with self.assertRaises(sandbox._ProtocolError): protocol.complete()

    def test_trusted_runner_sources_parse_and_reset_is_explicit(self):
        python=sandbox._batch_program('python_pure_v1')
        sql=sandbox._batch_program('sqlite_select_v1')
        ast.parse(python);ast.parse(sql)
        self.assertIn("'__builtins__':dict(builtins_template)",python)
        self.assertIn("copy.deepcopy(payload['case'])",python)
        self.assertIn("namespace =",python)
        tree=ast.parse(sql)
        observe=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='observe')
        self.assertTrue(any(isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='sql' for target in node.targets) and isinstance(node.value,ast.Name) and node.value.id=='source' for node in observe.body))
        self.assertIn("connection=sqlite3.connect(':memory:')",sql)
        self.assertIn('connection.set_authorizer(authorize)',sql)
        self.assertIn('connection.close()',sql)


@contextmanager
def fake_child(stdout_bytes):
    descriptors=[]
    streams=[]
    def pipe_data(data):
        reader,writer=os.pipe();descriptors.extend([reader,writer])
        if data: os.write(writer,data)
        os.close(writer);descriptors.remove(writer)
        stream=os.fdopen(reader,'rb',buffering=0);descriptors.remove(reader);streams.append(stream)
        return stream
    stdin_reader,stdin_writer=os.pipe();descriptors.append(stdin_reader)
    stdin=os.fdopen(stdin_writer,'wb',buffering=0);streams.append(stdin)
    child=Mock(pid=31337,stdin=stdin,stdout=pipe_data(stdout_bytes),stderr=pipe_data(b''),returncode=0)
    child.poll.return_value=0;child.wait.return_value=0
    try: yield child
    finally:
        for stream in streams:
            if not stream.closed: stream.close()
        for fd in descriptors: os.close(fd)


class OutputAccountingTests(unittest.TestCase):
    def test_exact_cap_then_eof_has_no_speculative_one_byte_read(self):
        before=[];after=[]
        with fake_child(b'1234') as child, tempfile.TemporaryDirectory() as d:
            with patch.object(sandbox.subprocess,'Popen',return_value=child),patch.object(sandbox,'_kill_group',return_value=cleanup_fixture()):
                result=sandbox._spawn(Path(d),Path(d)/'unused',[],b'',200,4,None,
                    before_output=lambda cost,pid:before.append((cost,pid)),
                    after_output=lambda cost,pid:after.append((cost,pid)))
        self.assertEqual(result['status'],'EXECUTED')
        self.assertEqual(result['stdout'],'1234')
        self.assertEqual(result['output_bytes'],4)
        self.assertEqual(result['output_reserved_bytes'],4)
        self.assertEqual(before,[(4,31337)]);self.assertEqual(after,[(4,31337)])

    def test_zero_available_pipe_hup_does_not_read_or_charge(self):
        before=[]
        with fake_child(b'') as child,tempfile.TemporaryDirectory() as d:
            with patch.object(sandbox.subprocess,'Popen',return_value=child),patch.object(sandbox,'_kill_group',return_value=cleanup_fixture()),patch.object(sandbox.os,'read',side_effect=AssertionError('EOF must not read')):
                result=sandbox._spawn(Path(d),Path(d)/'unused',[],b'',200,0,None,
                    before_output=lambda cost,pid:before.append(cost))
        self.assertEqual(result['status'],'EXECUTED')
        self.assertEqual(before,[])
        self.assertEqual(result['output_bytes'],0)

    def test_output_hook_rejection_is_before_read_and_reaps(self):
        class Stop(Exception): pass
        def reject(cost,pid):
            self.assertEqual((cost,pid),(5,31337))
            raise Stop('next cost exceeds four-byte cap')
        with fake_child(b'12345') as child,tempfile.TemporaryDirectory() as d:
            with patch.object(sandbox.subprocess,'Popen',return_value=child),patch.object(sandbox,'_kill_group',return_value=cleanup_fixture()) as reap,patch.object(sandbox.os,'read',side_effect=AssertionError('read after budget rejection')):
                with self.assertRaises(Stop): sandbox._spawn(Path(d),Path(d)/'unused',[],b'',200,4,None,before_output=reject)
        reap.assert_called_once()

    def test_short_read_reports_reserved_and_actual_separately(self):
        class Stop(Exception): pass
        before=[];after=[]
        def received(cost,pid):
            after.append((cost,pid));raise Stop('controlled stop after short receive')
        with fake_child(b'12345') as child,tempfile.TemporaryDirectory() as d:
            with patch.object(sandbox.subprocess,'Popen',return_value=child),patch.object(sandbox,'_kill_group',return_value=cleanup_fixture()),patch.object(sandbox.os,'read',return_value=b'12'):
                with self.assertRaises(Stop):
                    sandbox._spawn(Path(d),Path(d)/'unused',[],b'',200,10,None,
                        before_output=lambda cost,pid:before.append((cost,pid)),after_output=received)
        self.assertEqual(before,[(5,31337)]);self.assertEqual(after,[(2,31337)])

    def test_budget_exception_details_keep_cleanup_in_same_object(self):
        from verantyx.contract_ir import ContractError
        details={'phase':'child_output_bytes'}
        error=ContractError('OUTPUT_LIMIT','child_output_bytes','fixture',details)
        def reject(cost,pid): raise error
        with fake_child(b'12345') as child,tempfile.TemporaryDirectory() as d:
            with patch.object(sandbox.subprocess,'Popen',return_value=child),patch.object(sandbox,'_kill_group',return_value=cleanup_fixture(False)):
                with self.assertRaises(ContractError) as caught:
                    sandbox._spawn(Path(d),Path(d)/'unused',[],b'',200,4,None,before_output=reject)
        self.assertIs(caught.exception.details,details)
        self.assertFalse(details['cleanup']['leader_reaped'])
        self.assertTrue(details['cleanup']['group_signalled'])

    def test_deadline_and_user_interruption_have_distinct_no_launch_results(self):
        with tempfile.TemporaryDirectory() as d,patch.object(sandbox.subprocess,'Popen') as popen:
            expired=sandbox._spawn(Path(d),Path(d)/'unused',[],b'',200,1048576,None,deadline=time.monotonic()-1)
            interrupted=sandbox._spawn(Path(d),Path(d)/'unused',[],b'',200,1048576,True)
        self.assertEqual(expired['status'],'REQUEST_TIMEOUT')
        self.assertEqual(interrupted['status'],'INTERRUPTED')
        self.assertEqual(expired['launches'],0);popen.assert_not_called()


@unittest.skipUnless(os.environ.get('VERA_SANDBOX_INTEGRATION')=='1','root-owned actual OS worker only')
class ActualBatchTests(unittest.TestCase):
    def test_python_global_builtin_shadow_and_inputs_reset(self):
        source='counter=0\noriginal_len=len\ndef observe(items):\n    global counter,len\n    counter+=1\n    count=original_len(items)\n    len=lambda value: 999\n    items.append(7)\n    return [counter,count]'
        result=sandbox.run_artifact('python_pure_v1',source,{'name':'observe','parameters':['items']},[{'args':[[]]},{'args':[[0,-1]]},{'args':[[]]}])
        self.assertEqual(result['status'],'EXECUTED',result)
        self.assertEqual([row['value'] for row in result['results']],[[1,0],[1,2],[1,0]])
        self.assertEqual(result['stats']['launches'],2)
        self.assertEqual(result['stats']['cases_reserved'],3)
        self.assertEqual(result['stats']['cases_attempted'],3)
        self.assertEqual(result['stats']['cases_finished'],3)
        self.assertTrue(all(row['process_group_reaped'] for row in result['results']))
        # An intentionally mutating fixture is an EXECUTED observation, never
        # an input-effect certificate. Every case must retain that violation.
        self.assertTrue(all(row['mutation']['unchanged'] is False for row in result['results']))

    def test_sql_database_and_relation_reset(self):
        def case(rows): return {'tables':{'input_rows':{'schema':[{'name':'value','type':'INTEGER'}],'rows':rows}}}
        result=sandbox.run_artifact('sqlite_select_v1','SELECT value FROM input_rows ORDER BY value',{'columns':['value']},[case([[2],[1],[2]]),case([]),case([[0]])])
        self.assertEqual(result['status'],'EXECUTED',result)
        self.assertEqual([row['rows'] for row in result['results']],[[[1],[2],[2]],[],[[0]]])
        self.assertEqual(result['stats']['launches'],2)
        self.assertTrue(all(row['sqlite_version']=='3.53.2' for row in result['results']))


if __name__=='__main__': unittest.main()
