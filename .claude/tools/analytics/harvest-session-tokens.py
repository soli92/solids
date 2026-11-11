#!/usr/bin/env python3
# Shim: backward-compat wrapper → delegates to tools/analytics/harvest-session-tokens.py
import os, sys, subprocess
script_dir = os.path.dirname(os.path.abspath(__file__))
factory_root = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))
target = os.path.join(factory_root, 'tools', 'analytics', os.path.basename(__file__))
sys.exit(subprocess.call([sys.executable, target] + sys.argv[1:]))
