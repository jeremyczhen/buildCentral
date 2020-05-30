@echo off
rem = """ Do any custom setup like setting environment variables etc if required here ...
python -x "%~f0" %1 %2 %3 %4 %5 %6 %7 %8 %9
goto endofPython """

import os
import sys
import subprocess as sp

def guess_project_root():
    signature = set(['external', 'workspace', 'project', 'tools'])
    cur_dir = os.getcwd()
    parent_dir = os.path.abspath(os.path.join(cur_dir, os.pardir))
    while (parent_dir != cur_dir):
        if signature.issubset(set(os.listdir(cur_dir))):
            break
        cur_dir = parent_dir
        parent_dir = os.path.abspath(os.path.join(cur_dir, os.pardir))
    if os.path.dirname(os.path.realpath(cur_dir)) == cur_dir:
        print('Cannot fild project root! Please enter a project and run again.')
        cur_dir = None
    return cur_dir

project_root = guess_project_root()
if (project_root):
    bc = os.path.join(project_root, 'tools', 'buildCentral')
    if sys.argv[0][-7:] == 'gmk.cmd':
        bc = os.path.join(bc, 'gbuild_central.py')
        os.system(bc)
    else:
        bc = os.path.join(bc, 'build_central.py')
        sp.call([bc] + sys.argv[1:], shell=True)

rem = """
:endofPython """
