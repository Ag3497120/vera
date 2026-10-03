"""Count the learned counters of a placement (table `counters`) that the W5-b TIME rule applies to: a unit that begins with a TIME_UNITS entry
and is longer than it (coarse_types._time_unit_head).  Read-only.  Usage: python count_time_head_counters.py <placement dir>"""
import sqlite3
import sys

from verantyx import coarse_types as ct

con = sqlite3.connect("file:%s/placement.sqlite?mode=ro" % sys.argv[1], uri=True)
units = sorted(r[0] for r in con.execute("SELECT unit FROM counters"))
hit = [u for u in units if u not in ct.TIME_UNITS and ct._time_unit_head(u) is not None and len(u) <= 6]
print("counters_total", len(units))
print("time_head_units", len(hit))
print(" ".join(hit))
