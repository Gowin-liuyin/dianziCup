"""Measure actual Python interpreter CPU for the child check, including failed runs."""

import json
import os
import runpy
import sys
import time

arguments = sys.argv[1:]
sys.path.insert(0, os.getcwd())
started = time.process_time()
try:
    if arguments[0] == "-m":
        sys.argv = [arguments[1], *arguments[2:]]
        runpy.run_module(arguments[1], run_name="__main__", alter_sys=True)
    else:
        sys.argv = arguments
        runpy.run_path(arguments[0], run_name="__main__")
finally:
    print("CPU_RECEIPT=" + json.dumps({"cpu_seconds": time.process_time() - started}))
