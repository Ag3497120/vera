"""Print the failed or errored test ids in a junit xml, sorted (one per line)."""
import sys
import xml.etree.ElementTree as ET
ids = set()
for case in ET.parse(sys.argv[1]).getroot().iter("testcase"):
    if case.find("failure") is not None or case.find("error") is not None:
        ids.add(f"{case.get('classname')}::{case.get('name')}")
print("\n".join(sorted(ids)))
