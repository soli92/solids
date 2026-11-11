#!/usr/bin/env python3
# Shim: backward-compat wrapper → delegates to tools/runtime/suggest-next.py
import os
import sys
import subprocess

script_dir = os.path.dirname(os.path.abspath(__file__))
factory_root = os.path.dirname(os.path.dirname(script_dir))
target = os.path.join(factory_root, "tools", "runtime", "suggest-next.py")
sys.exit(subprocess.call([sys.executable, target] + sys.argv[1:]))
