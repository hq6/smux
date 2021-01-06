#!/usr/bin/env python3

# Copyright (c) 2014-2020 Henry Qin
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

__doc__ = """smux.py <session_spec_file>

The format of session_spec_file consists of ini-style parameters followed by
lists of commands delimited by lines beginning with '---'.

Currently there are four supported parameters.

PANES_PER_WINDOW,
    The number of panes that each window will be carved into.

LAYOUT,
    One of the five standard tmux layouts, given below.
    even-horizontal, even-vertical, main-horizontal, main-vertical, tiled.

NO_CREATE,
    When given (no parameter value), smux will attempt to send the commands
    to the caller's window. Option is ignored if more than one command
    sequence if given, or caller is not inside a tmux session.

USE_THREADS,
    When given (no parameter value), smux will use a different thread for
    sending commands to each pane. It will not exit until all the threads
    are joined. This parameter is ignored when NO_CREATE is given, or when
    there is only one list of commands.

There are three types of commands that can appear in an smux file.
1. Ordinary commands are sent to the target pane without modification as if a
   user had typed them by hand.
2. Comments are lines that begin with `#` and are ignored.
3. #smux directives, which are lines beginning with `#smux ` and invoke special
   functionality inside the smux itself. The currently supported #smux
   directive are described in the following section.

#smux directives
----------------
paste-buffer [args]
  Identical to tmux paste-buffer, except with the pane already specified.
send-keys [args]
  Identical to tmux send-keys, except with the pane already specified.
  This is useful for sending special keys such as `Enter`, since smux's
  normal mode of operation is to send all keys literally.
waitForString <string> [pollingInterval] [numLinesToExamine]
  Wait until the given string appears in the last line of the target pane
  before executing or sending the next command. Note that this directive
  polls on the output of `tmux capture-pane`, so it only works reliably if
  the string it is waiting for appears on the screen and stays on the
  screen persistently until user input is received. That means it is
  appropriate for waiting for shell or password prompts, but not waiting
  for a particular line to appear in a streaming log. The polling interval
  (default 1 second) and the number of lines examined can be overriden by
  passing additional arguments.
waitForRegex <regex> [pollingInterval] [numLinesToExamine]
  Identical to waitForString except that the first argument is treated as a
  Python regular expression rather than a literal string.
shell <args>
  Execute a shell command using `/bin/sh`. The variables $window and $pane
  are exported for use by the command. Output is not captured by smux.
  Each instance of this directive runs in a separate shell.
sleep <seconds>
  Sleep for a given number of seconds before executing or sending the next
  command.


Sample Input File:

    # This is a comment
    PANES_PER_WINDOW = 4
    LAYOUT = tiled
    ----------
    echo 'This is pane 1'
    cat /proc/cpuinfo | less
    ----------
    echo 'This is pane 2'
    cat /proc/meminfo
    ----------
    echo 'This is pane 3'
    uname -a
    ----------
    echo "This is pane 4"
    cat /etc/issue
    ----------

"""
__all__ = ['create',]


import argparse
import os
import sys
import time
import re
from subprocess import Popen, PIPE
import traceback
import shlex
import threading

totalPanes = 0
MAX_PANES = 500

################################################################################
# Core utility functions. These are define dfirst because global variable
# assignments depend on them.
################################################################################
def tcmd(cmd):
    """Execute the given tmux command synchronously and ignore any output."""
    os.system("tmux %s" % cmd)


def tget(cmd):
    """Execute the given tmux command synchronously and return any output."""
    proc = Popen("tmux %s" % cmd, stdout=PIPE, stderr=PIPE, shell=True)
    out, err = proc.communicate()
    exitcode = proc.returncode
    return out
################################################################################

# Figure out at process start whether we are inside a tmux session.
tmux = os.environ.get('TMUX')

# The name of either the current session or new session created by smux.py.
# Note that the existence of this variable implies that a single `smux.create`
# call can be active at any point in time in a given process.
sessionName = None
if tmux:
    sessionName = tget("display-message -p '#{session_name}'").decode('utf-8').strip()


def splitWindow():
    """Split the current pane horizontally."""
    global totalPanes
    global MAX_PANES
    if totalPanes < MAX_PANES:
        tcmd("split-window -d -h")
        totalPanes += 1


def newWindow():
    """Create a new tmux window and make it current."""
    global totalPanes
    global MAX_PANES
    if totalPanes < MAX_PANES:
        tcmd("new-window")
        totalPanes += 1


def getCurrentWindow():
    """Retrieve the current window index as an int."""
    return int(tget("display-message -p '#I'"))


def getCurrentPane():
    """Retrieve the current pane index as an int."""
    return int(tget("display-message -p '#P'"))


def carvePanes(numPanes, layout):
    """
    Cut the current window into panes and set the requested layout.

    Parameters
    ----------
    numPanes: int
      The number of panes to cut the current window into.
    layout: string
      The name of one of the tmux preset layouts to use for the window that the
      panes are being carved out of. Must be one of the following strings:
      "even-horizontal", "even-vertical", "main-horizontal", "main-vertical",
      "tiled".
    """
    for i in range(numPanes - 1):
        splitWindow()
        tcmd("select-layout %s" % layout)
    tcmd("select-layout %s" % layout)
    return getCurrentWindow()


def waitForStringOrRegex(window, pane, args, isRegex):
    """
    Block calling thread until the given string or regex appears in the specified pane.

    Parameters
    ----------
    window: int
      The window index, equivalent to the value returned by
      `display-message #{window_index}` in the target window.
    pane: int
      The pane index, equivalent to the value returned by
      `display-message #{pane_index}` in the target pane.
    args: list(str)
      The arguments given by the user in the `#smux` directive.
       * args[0] is assumed to be the string or regex searched we seek.
       * args[1] if given, is the polling interval at which to poll for the
         desired string or regex.
       * args[2], if given, is the number of physical (displayed, not logical)
         lines from the bottom of the pane to look for the target string or regex.
    isRegex: bool
      True means the args[0] should be treated as a regex.
    """
    if len(args) == 0:
        print("waitForString or waitForRegex offered without mandatory argument, ignoring")
        return

    # This will be treated as either string or regex depending on isRegex.
    needle = args[0]
    regexNeedle = re.compile(needle) if isRegex else None

    pollingInterval = 1.0
    numLinesToCapture = 1
    if len(args) > 1:
        pollingInterval = float(args[1])
    if len(args) > 2:
        numLinesToCapture = int(args[2])
    while True:
        time.sleep(pollingInterval)

        # Join lines so that we can capture a string spanning multiple lines.
        rawHayStack = tget(
            f"capture-pane -t ={sessionName}:{window}.{pane} -p").decode('utf-8')
        # Need to strip to remove the trailing newline from output of capture-pane.
        haystack = ''.join(rawHayStack.strip().split('\n')
                           [-numLinesToCapture:])

        if isRegex:
            if regexNeedle.search(haystack):
                return
        else:
            if needle in haystack:
                return


def digestCommands(commands):
    r"""
    Remove comments and empty lines and join #smux commands.

    Lines that start with `#` but not `#smux` are comments.
    Lines that start with `#smux` and end with `\` are merged with subsequent
    lines recursively.
    Lines ending with `\` that are not part of a chain of consecutive lines
    starting with `#smux` are left untouched.

    Before:
      # This is a comment.

      #smux shell echo \
      Hello \
      smux

      echo Hello \
      World

    After:
      #smux shell echo Hello smux
      echo Hello \
      World

    Parameters
    ----------
    commands: list(str)
      A list of raw commands from a call to `create`.

    Returns
    -------
    list(str)
      A list of strings with comments removed and #smux lines joined.
    """
    rawCommands = [x for x in commands if x != '' and (
        x.startswith("#smux ") or not x.startswith("#"))]
    digestedCommands = []
    bufferedLine = None
    for line in rawCommands:
        # The previous line initiated a continuation.
        if bufferedLine:
            bufferedLine += line

            # Check if next line should be joined.
            if bufferedLine.endswith("\\"):
                bufferedLine = bufferedLine[:-1]
            else:
                digestedCommands.append(bufferedLine)
                bufferedLine = None
        # Previous line did not initiate or continue a continuation.
        else:
            if line.startswith("#smux ") and line.endswith("\\"):
                bufferedLine = line[:-1]
            else:
                digestedCommands.append(line)
    # The last line ended in a continuation for some reason.
    if bufferedLine:
        digestedCommands.append(bufferedLine)
    return digestedCommands


def sendCommand(cmd, pane=0, window=None):
    """
    Send or execute a given command against a given pane.

    This function examines the input string. If it begins with `#smux `, then
    it is interpretted as a special function for smux itself to execute in the
    context of the target pane. Otherwise, it is sent to the target pane as if
    a human had typed it. See smux.__doc__ for a description of the various
    #smux directives.

    Parameters
    ----------
    cmd: string
      The command to either execute or send to the target window and pane.
    window: int
      The window index, equivalent to the value returned by
      `display-message #{window_index}` in the target window.
    pane: int
      The pane index, equivalent to the value returned by
      `display-message #{pane_index}` in the target pane.
    """
    def prepareCommand(cmd):
        """
        "Escape" a string for use with send-keys.

        Deal with single quotes inside command by spliting the command by single
        quotes, wrapping the single quotes in double quotes, and wrapping the
        other parts in single quotes.
        """
        if not "'" in cmd:
            return f"'{cmd}'"
        return '"\'"'.join(f"'{x}'" for x in cmd.split("'"))

    time.sleep(0.1)
    if not window:
        window = getCurrentWindow()
    # If the command is a directive to smux itself, then execute it instead of
    # sending it to the pane directly.
    if cmd.startswith("#smux "):
        # Skip the #smux prefix.
        args = shlex.split(cmd)[1:]
        if args[0] == 'paste-buffer':
            tcmd(f"paste-buffer -t '={sessionName}:{window}.{pane}' " + shlex.join(args[1:]))
        elif args[0] == 'send-keys':
            # This option is useful for sending something like "Enter" with
            # semantic meaning, rather than literally. This is needed rather
            # than just allowing the script to directly invoke `tmux send-keys`
            # because the target pane may be running a completely different
            # process which we want to feed special input to (e.g. it is waiting
            # for the user to type a special key such as Enter).
            tcmd(f"send-keys -t '={sessionName}:{window}.{pane}' " + shlex.join(args[1:]))
        elif args[0] == 'sleep':
            time.sleep(float(args[1]))
        elif args[0] == 'shell':
            # Use the suffix of the original string, because
            # shlex.join(shlex.split(X))  turns double-quotes into
            # single-quotes, which is undesirable for expading variables.
            fullCommand = f'export session_name={sessionName}; export window={window}; ' + \
                f'export pane={pane}; ' + cmd[cmd.index("shell") + len("shell"):]
            os.system(fullCommand)
        elif args[0] == 'waitForString':
            # This command and waitForRegex relies on capture-pane polling (not
            # pipe-pane), which implies that it only works if the string we are
            # waiting for sticks around on the screen for a while, rather than
            # scrolling by.
            waitForStringOrRegex(window, pane, args[1:], False)
        elif args[0] == 'waitForRegex':
            waitForStringOrRegex(window, pane, args[1:], True)
        return

    tcmd(f"send-keys -t ={sessionName}:{window}.{pane} -l " + prepareCommand(cmd))
    tcmd(f"send-keys -t ={sessionName}:{window}.{pane} Enter")


# Capture these variables on import if we are inside a tmux, so that their
# values do not change if the user moves around after invoking a slow command
# with noCreate.
if tmux:
    callerWindow = getCurrentWindow()
    callerPane = getCurrentPane()


def create(numPanesPerWindow, commands, layout='tiled', executeAfterCreate=None, noCreate=False, useThreads=False):
    """
    Create a set of tmux panes and run each command list in commands in its own pane.

    Parameters
    ----------
    numPanesPerWindow: int
      The number of panes to create in each window. If there are more lists of
      commands than numPanesPerWindow, more windows will be created.
    commands : list(list(str))
      A list of command lists. Each command list will be send to a given pane.
      The types of commands are documented in smux.__doc__.
    executeAfterCreate : Callable[[], None]
      A function that a client can pass in to be executed after creating the
      windows. For example, one can synchronize the panes by passing the following:
      lambda : smux.tcmd("setw synchronize-panes on")
    noCreate : bool
      True means smux should send the commands to the pane that the caller lives
      in, rather than creating new panes. Ignored if more than one command list
      is given, or caller is not currently running in a tmux session.
      This can be useful for using smux to ssh into a machine and then run
      commands inside the ssh session.
    useThreads: bool
      True means that smux will handle the commands for each pane using different
      threads, so that if a command includes a slow pragma such as #smux sleep,
      it will not slow down the execution of commands in other panes.
      This should be to False unless the caller is certain that the commands in
      different panes are independent of each other's timing.
    """

    def sendCommandList(commandList, window, pane):
        """
        Send a set of commands to the given pane pane.

        This function is needed because lambdas cannot accept for loops for
        threads.
        """
        # Sleep for 500 ms to give time for the tty to notice its new
        # dimensions. Empirically, this prevents commands like `man tmux` from
        # rendering with incorrect dimensions.
        time.sleep(0.5)
        for command in commandList:
            sendCommand(command, pane, window)

    global sessionName
    # Remove comments in commands and join together line-continuations for #smux
    # commands.
    for i in range(len(commands)):
        commands[i] = digestCommands(commands[i])

    if not numPanesPerWindow > 0:
        print("No panes specified.")
        return
    if numPanesPerWindow > 30:
        print("Number per window must be less than 30!")
        return
    if noCreate and (not tmux or len(commands) != 1):
        print("noCreate parameter ignored because we are not in a tmux session or len(commands) != 1")
    if not tmux:
        rows, columns = os.popen('stty size', 'r').read().split()
        sessionName = tget(f"new-session -d -x {columns} -y {rows} -P -F '#{{session_name}}'").decode('utf-8').strip()
    elif noCreate and len(commands) == 1:
        # Run ourselves in a subshell, so that Python does not consume the input
        # intended for the new foreground processes started by the script.
        if not os.environ.get('SMUX_SUBSHELL'):
            os.system(
                f'SMUX_SUBSHELL=1 CALLER_WINDOW={callerWindow} CALLER_PANE={callerPane} {shlex.join(sys.argv)} & > /dev/null 2>&1')
            return

        # Target the current window that invoked this command.
        currentWindow = int(os.environ.get("CALLER_WINDOW"))
        currentPane = int(os.environ.get("CALLER_PANE"))
        sendCommandList(commands[0], currentWindow, currentPane)
        return
    else:
        newWindow()

    panesNeeded = len(commands)
    # There is no benefit to threads if there is only one pane
    useThreads = useThreads and panesNeeded > 1
    threads = []
    while panesNeeded > 0:
        windowNum = carvePanes(numPanesPerWindow, layout)
        panesNeeded -= numPanesPerWindow

        # Send the commands in with CR
        for i in range(min(numPanesPerWindow, len(commands))):
            print(i)
            if useThreads:
                # We use a list comprehension because Python disallows for loops in lists.
                thread = threading.Thread(
                    target=sendCommandList, args=(commands[i], windowNum, i))
                thread.start()
                threads.append(thread)
            else:
                sendCommandList(commands[i], windowNum, i)

        # Pop off the commands we just finished with
        for i in range(min(numPanesPerWindow, len(commands))):
            commands.pop(0)

        # Create a new window if necessary
        if panesNeeded > 0:
            newWindow()

    for thread in threads:
        thread.join()

    # It is important to run this after the threads are joined, because only
    # then can we be guaranteed that all panes are truly finished creating.
    if executeAfterCreate:
        executeAfterCreate()

    if not tmux:
        tcmd("attach-session")

def startSession(file_):
    """
    Start a tmux session by parsing the given file for options and commands.

    Options are documented at the top of the file.
    """
    cmds = []

    args = {"PANES_PER_WINDOW": None, "LAYOUT": "tiled", "NO_CREATE": False,
            "USE_THREADS": False}
    cur_cmds = None
    for line in file_:
        line = line.strip()
        # comments
        if line == '' or (line.startswith("#") and not line.startswith("#smux ")):
            continue
        # Start a new pane specification
        if line.startswith("---"):
            if cur_cmds is not None:
                cmds.append(cur_cmds)
            cur_cmds = []
            continue
        # Configuration part
        if cur_cmds == None:
            try:
                if line == 'NO_CREATE':
                    args["NO_CREATE"] = True
                elif line == 'USE_THREADS':
                    args['USE_THREADS'] = True
                else:
                    left, right = line.split('=', 1)
                    args[left.strip()] = right.strip()
            except:
                print("Argment '%s' ignored" % line)
                print("Arguments must be in the form of key = value")
                continue

        else:  # Actual session is being added to
            cur_cmds.append(line.strip())

    if cur_cmds:
        cmds.append(cur_cmds)

    if args['PANES_PER_WINDOW'] is not None:
        panes_per_window = int(args['PANES_PER_WINDOW'])
    else:
        panes_per_window = len(cmds)
    create(panes_per_window, cmds, args['LAYOUT'], noCreate=args['NO_CREATE'],
           useThreads=args['USE_THREADS'])


def usage():
    print(__doc__)
    sys.exit(1)


def main():
    """Entry point for the script."""
    # Using argparse mostly for handling `-` for stdin.
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawTextHelpFormatter,
                                     add_help=False)
    # Manually defined so we can have backwards compatible `-?`.
    parser.add_argument('--help', '-h', '-?',  action="store_true", help="Show this text and exit.")
    parser.add_argument('session_spec_file', nargs='?',
                         type=argparse.FileType('r'),
                         help="A file containing options, shell commands and smux directives to run in each pane.")

    options = parser.parse_args(sys.argv[1:])
    if options.help or options.session_spec_file is None:
        usage()
    try:
        startSession(options.session_spec_file)
    finally:
        options.session_spec_file.close()


if __name__ == "__main__":
    main()
