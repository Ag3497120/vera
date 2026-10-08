# Review probe (W2-b2 r1): simulate the polling thread being descheduled between
# AgentRuntime._read_output and AgentRuntime._process_running in AgentRuntime.poll.
# The patched check waits until the supervisor has written its status (so all output is
# already on disk) and has exited, then asks the original question.  No product file changes.
import os, time
from verantyx import agent_runtime

_orig = agent_runtime.AgentRuntime._process_running


def _late(self, handle):
    status = handle.session_dir / "agent.status.json"
    deadline = time.time() + 20
    while not status.exists() and time.time() < deadline:
        time.sleep(0.01)
    time.sleep(0.3)
    return _orig(self, handle)


if os.environ.get("REVIEW_RACE") == "1":
    agent_runtime.AgentRuntime._process_running = _late
