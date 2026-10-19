"""Use the approved base interpreter and the product virtualenv's installed packages."""

import runpy
import site
import sys

site.addsitedir("D:/dianzi/backend/.venv/Lib/site-packages")
module = sys.argv.pop(1)
sys.argv[0] = module
runpy.run_module(module, run_name="__main__", alter_sys=True)
