"""r3 self-authored cleanup injections; all process/signal/I/O calls are mocked.

These fixtures establish failure plumbing, not actual OS isolation. The root's
single worker owns execution; no sealed or independently evaluated input is used.
"""
import errno
from pathlib import Path
import selectors
import signal
import subprocess
import unittest
from unittest.mock import Mock, patch

from verantyx import contract_sandbox as sandbox
from verantyx.contract_ir import ContractError


def confirmed_cleanup():
    return {'group_signalled':True,'leader_reaped':True,
            'group_absence_confirmed':True,'cleanup_error':None,
            'deadline_exceeded':False,'child_id':31337}


def fake_process():
    streams={name:Mock(name=name,closed=False) for name in ('stdin','stdout','stderr')}
    for stream in streams.values(): stream.fileno.return_value=99
    process=Mock(pid=31337,returncode=0,**streams)
    process.poll.return_value=0
    process.wait.return_value=0
    return process


def spawn(**kwargs):
    return sandbox._spawn(Path('/unused-cleanup-fixture'),Path('/unused-cleanup-fixture/policy.sb'),
                          [],b'',200,1048576,None,**kwargs)


class CleanupProtectionTests(unittest.TestCase):
    def test_selector_constructor_failure_preserves_launch_and_closes_all_pipes(self):
        child=fake_process()
        failure=OSError(errno.EMFILE,'authored selector fixture')
        with patch.object(sandbox.subprocess,'Popen',return_value=child),patch.object(sandbox.selectors,'DefaultSelector',side_effect=failure),patch.object(sandbox,'_kill_group',return_value=confirmed_cleanup()) as reap:
            result=spawn()
        self.assertEqual(result['status'],'SANDBOX_UNAVAILABLE')
        self.assertEqual(result['launches'],1)
        self.assertEqual(result['output_bytes'],0)
        reap.assert_called_once()
        for name in ('stdin','stdout','stderr'): getattr(child,name).close.assert_called_once()
        self.assertTrue(result['cleanup']['leader_reaped'])
        self.assertTrue(result['cleanup']['group_absence_confirmed'])

    def test_selector_registration_failure_has_same_cleanup_protection(self):
        child=fake_process();selector=Mock()
        selector.register.side_effect=OSError(errno.EBADF,'authored registration fixture')
        with patch.object(sandbox.subprocess,'Popen',return_value=child),patch.object(sandbox.selectors,'DefaultSelector',return_value=selector),patch.object(sandbox.os,'set_blocking'),patch.object(sandbox,'_kill_group',return_value=confirmed_cleanup()) as reap:
            result=spawn()
        self.assertEqual(result['status'],'SANDBOX_UNAVAILABLE')
        self.assertEqual(result['launches'],1)
        reap.assert_called_once();selector.close.assert_called_once()
        for name in ('stdin','stdout','stderr'): getattr(child,name).close.assert_called_once()

    def test_pipe_close_failure_does_not_skip_other_pipes_or_become_success(self):
        child=fake_process()
        child.stdin.close.side_effect=OSError('authored pipe close fixture')
        with patch.object(sandbox.subprocess,'Popen',return_value=child),patch.object(sandbox.selectors,'DefaultSelector',side_effect=OSError('setup fixture')),patch.object(sandbox,'_kill_group',return_value=confirmed_cleanup()):
            result=spawn()
        self.assertEqual(result['status'],'EXECUTION_INCOMPLETE')
        self.assertEqual(result['prior_status'],'SANDBOX_UNAVAILABLE')
        self.assertFalse(result['process_group_reaped'])
        self.assertEqual(result['cleanup']['cleanup_error'][0]['stage'],'close_stdin')
        for name in ('stdin','stdout','stderr'): getattr(child,name).close.assert_called_once()

    def test_budget_exception_object_survives_selector_and_pipe_cleanup_errors(self):
        child=fake_process();selector=Mock();details={'phase':'authored fixture'}
        original=ContractError('VERIFICATION_BUDGET','witnesses','authored budget fixture',details)
        selector.register.side_effect=original
        selector.close.side_effect=RuntimeError('authored selector close fixture')
        child.stdin.close.side_effect=ValueError('authored stream close fixture')
        with patch.object(sandbox.subprocess,'Popen',return_value=child),patch.object(sandbox.selectors,'DefaultSelector',return_value=selector),patch.object(sandbox.os,'set_blocking'),patch.object(sandbox,'_kill_group',return_value=confirmed_cleanup()):
            with self.assertRaises(ContractError) as caught: spawn()
        self.assertIs(caught.exception,original)
        self.assertIs(caught.exception.details,details)
        self.assertEqual(details['child_attempt']['launches'],1)
        self.assertEqual([e['stage'] for e in details['cleanup']['cleanup_error']],['selector_close','close_stdin'])
        for name in ('stdin','stdout','stderr'): getattr(child,name).close.assert_called_once()

    def test_cleanup_helper_failure_does_not_mask_budget_exception(self):
        child=fake_process();selector=Mock();details={}
        original=ContractError('REQUEST_TIMEOUT','execution','authored timeout fixture',details)
        selector.register.side_effect=original
        with patch.object(sandbox.subprocess,'Popen',return_value=child),patch.object(sandbox.selectors,'DefaultSelector',return_value=selector),patch.object(sandbox.os,'set_blocking'),patch.object(sandbox,'_kill_group',side_effect=PermissionError('authored cleanup fixture')):
            with self.assertRaises(ContractError) as caught: spawn()
        self.assertIs(caught.exception,original)
        self.assertFalse(details['cleanup']['group_absence_confirmed'])
        self.assertEqual(details['cleanup']['cleanup_error'][0]['stage'],'group_cleanup')
        for name in ('stdin','stdout','stderr'): getattr(child,name).close.assert_called_once()

    def test_contract_error_without_dictionary_details_still_serializes_cleanup(self):
        for original_details in (None,['authored details fixture']):
            with self.subTest(original_details=original_details):
                child=fake_process();selector=Mock()
                original=ContractError('VERIFICATION_BUDGET','witnesses','authored fixture',original_details)
                selector.register.side_effect=original
                with patch.object(sandbox.subprocess,'Popen',return_value=child),patch.object(sandbox.selectors,'DefaultSelector',return_value=selector),patch.object(sandbox.os,'set_blocking'),patch.object(sandbox,'_kill_group',return_value=confirmed_cleanup()):
                    with self.assertRaises(ContractError) as caught: spawn()
                self.assertIs(caught.exception,original)
                self.assertEqual((original.code,original.stage),('VERIFICATION_BUDGET','witnesses'))
                self.assertIs(original.details['original_details'],original_details)
                self.assertTrue(original.to_dict()['details']['cleanup']['group_absence_confirmed'])
                self.assertEqual(original.to_dict()['details']['child_attempt']['launches'],1)

    def test_environment_failure_preserves_partial_reserved_and_actual_output(self):
        child=fake_process();selector=Mock();before=[];after=[]
        selector.get_map.return_value={1:object()}
        key=selectors.SelectorKey(child.stdout,99,selectors.EVENT_READ,'stdout')
        selector.select.side_effect=[[(key,selectors.EVENT_READ)],OSError('authored select fixture')]
        with patch.object(sandbox.subprocess,'Popen',return_value=child),patch.object(sandbox.selectors,'DefaultSelector',return_value=selector),patch.object(sandbox.os,'set_blocking'),patch.object(sandbox,'_available_bytes',return_value=3),patch.object(sandbox.os,'read',return_value=b'abc'),patch.object(sandbox,'_kill_group',return_value=confirmed_cleanup()):
            result=spawn(before_output=lambda cost,pid:before.append((cost,pid)),after_output=lambda cost,pid:after.append((cost,pid)))
        self.assertEqual(result['status'],'SANDBOX_UNAVAILABLE')
        self.assertEqual(result['stdout'],'abc')
        self.assertEqual((result['launches'],result['output_reserved_bytes'],result['output_bytes']),(1,3,3))
        self.assertEqual(before,[(3,31337)]);self.assertEqual(after,[(3,31337)])

    def test_group_presence_even_after_leader_wait_rejects_success(self):
        child=fake_process();selector=Mock();selector.get_map.return_value={}
        cleanup=confirmed_cleanup();cleanup['group_absence_confirmed']=False
        with patch.object(sandbox.subprocess,'Popen',return_value=child),patch.object(sandbox.selectors,'DefaultSelector',return_value=selector),patch.object(sandbox.os,'set_blocking'),patch.object(sandbox,'_kill_group',return_value=cleanup):
            result=spawn()
        self.assertEqual(result['status'],'EXECUTION_INCOMPLETE')
        self.assertFalse(result['process_group_reaped'])
        self.assertTrue(result['cleanup']['leader_reaped'])


class GroupObservationTests(unittest.TestCase):
    def test_positive_control_requires_wait_and_owned_group_absence(self):
        child=fake_process()
        with patch.object(sandbox.os,'killpg',side_effect=[None,ProcessLookupError('absent')]) as kill,patch.object(sandbox.time,'monotonic',return_value=0):
            cleanup=sandbox._kill_group(child,.1)
        self.assertTrue(sandbox._cleanup_confirmed(cleanup))
        child.wait.assert_called_once()
        self.assertEqual(kill.call_args_list[0].args,(31337,signal.SIGKILL))
        self.assertEqual(kill.call_args_list[1].args,(31337,0))

    def test_already_absent_group_does_not_claim_a_signal_was_delivered(self):
        child=fake_process()
        with patch.object(sandbox.os,'killpg',side_effect=ProcessLookupError('already absent')),patch.object(sandbox.time,'monotonic',return_value=0):
            cleanup=sandbox._kill_group(child,.1)
        self.assertFalse(cleanup['group_signalled'])
        self.assertTrue(sandbox._cleanup_confirmed(cleanup))

    def test_persistent_group_is_not_reaped_even_when_leader_wait_succeeds(self):
        child=fake_process()
        with patch.object(sandbox.os,'killpg') as kill,patch.object(sandbox.time,'monotonic',side_effect=[0,0,0,0,.1,.1]),patch.object(sandbox.time,'sleep'):
            cleanup=sandbox._kill_group(child,.1)
        self.assertTrue(cleanup['leader_reaped'])
        self.assertFalse(cleanup['group_absence_confirmed'])
        self.assertTrue(cleanup['deadline_exceeded'])
        self.assertFalse(sandbox._cleanup_confirmed(cleanup))
        self.assertEqual(kill.call_count,2)

    def test_permission_error_is_unknown_absence(self):
        child=fake_process()
        with patch.object(sandbox.os,'killpg',side_effect=[None,PermissionError('probe denied')]),patch.object(sandbox.time,'monotonic',return_value=0):
            cleanup=sandbox._kill_group(child,.1)
        self.assertTrue(cleanup['leader_reaped'])
        self.assertFalse(cleanup['group_absence_confirmed'])
        self.assertEqual(cleanup['cleanup_error'][0]['stage'],'group_probe')
        self.assertFalse(sandbox._cleanup_confirmed(cleanup))

    def test_signal_error_is_not_erased_by_later_absence(self):
        child=fake_process()
        with patch.object(sandbox.os,'killpg',side_effect=[PermissionError('signal denied'),ProcessLookupError('absent')]),patch.object(sandbox.time,'monotonic',return_value=0):
            cleanup=sandbox._kill_group(child,.1)
        self.assertFalse(cleanup['group_signalled'])
        self.assertTrue(cleanup['group_absence_confirmed'])
        self.assertFalse(sandbox._cleanup_confirmed(cleanup))

    def test_expired_cleanup_deadline_does_not_invent_absence(self):
        child=fake_process()
        with patch.object(sandbox.os,'killpg') as kill,patch.object(sandbox.time,'monotonic',return_value=10):
            cleanup=sandbox._kill_group(child,.2,deadline=9)
        child.wait.assert_called_once_with(timeout=0)
        self.assertTrue(cleanup['deadline_exceeded'])
        self.assertFalse(cleanup['group_absence_confirmed'])
        self.assertFalse(sandbox._cleanup_confirmed(cleanup))
        kill.assert_called_once_with(31337,signal.SIGKILL)

    def test_leader_wait_timeout_is_not_reclassified_as_reap(self):
        child=fake_process();child.wait.side_effect=subprocess.TimeoutExpired('authored fixture',.1)
        with patch.object(sandbox.os,'killpg',side_effect=[None,ProcessLookupError('absent')]),patch.object(sandbox.time,'monotonic',return_value=0):
            cleanup=sandbox._kill_group(child,.1)
        self.assertFalse(cleanup['leader_reaped'])
        self.assertTrue(cleanup['group_absence_confirmed'])
        self.assertFalse(sandbox._cleanup_confirmed(cleanup))


class ProfileEvidenceTests(unittest.TestCase):
    def test_shell_descendants_are_unverified_without_any_launch(self):
        with patch.object(sandbox,'_spawn') as child:
            result=sandbox.run_artifact('posix_numeric_stream_v1',"/usr/bin/awk '{print $1}'",{},[{'stdin':'0\n','argv':[]}])
        self.assertEqual(result['status'],'DESCENDANT_ISOLATION_UNVERIFIED')
        self.assertIsNone(result['code'])
        self.assertEqual((result['stats']['launches'],result['stats']['cases']),(0,0))
        child.assert_not_called()

    def test_fork_denial_is_an_explicit_probe_obligation(self):
        self.assertIn('child=os.fork()',sandbox._PROBE)
        self.assertIn("checks['fork_denied']=True",sandbox._PROBE)
        self.assertIn('(deny process-fork)',sandbox._policy(Path('/unused-policy-fixture'),'python_pure_v1'))


if __name__=='__main__': unittest.main()
