from sniffer.api import *
import os, termstyle

# you can customize the pass/fail colors like this
pass_fg_color = termstyle.green
pass_bg_color = termstyle.bg_default
fail_fg_color = termstyle.red
fail_bg_color = termstyle.bg_default

# All lists in this variable will be under surveillance for changes.
watch_paths = ['.', 'tests/', 'pydocspell/']

# this gets invoked on every file that gets changed in the directory. Return
# True to invoke any runnable functions, False otherwise.
#
# This fires runnables only if files ending with .py extension and not prefixed
# with a period.
@file_validator
def py_files(filename):
    return filename.endswith('.py') and not os.path.basename(filename).startswith('.')


pytest_args = [
    '--color=no',
    '--tb=native',
    '--showlocals',
    #'--exitfirst',
    #'--capture=no',
    '--show-capture=stdout',
    '--show-capture=stderr',
    '--show-capture=log',
    '-rfExP',
]

try:
    import ipdb;
    pytest_args.append('--pdbcls=IPython.terminal.debugger:TerminalPdb')
except ImportError:
    pass

try:
    import flake8
    pytest_args.append('--flake8')
except ImportError:
    pass





# This gets invoked for verification. This is ideal for running tests of some sort.
# For anything you want to get constantly reloaded, do an import in the function.
#
# sys.argv[0] and any arguments passed via -x prefix will be sent to this function as
# it's arguments. The function should return logically True if the validation passed
# and logicially False if it fails.
@runnable
def execute_pytest(*args):
    import pytest
    pytest_args.extend(args[1:])
    return pytest.main(pytest_args) == 0
