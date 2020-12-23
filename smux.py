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

import os
import sys
import time
from subprocess import Popen, PIPE
import traceback
import shlex

totalWindows = 0
MAX_WINDOWS=500

def tcmd(cmd):
   os.system("tmux %s" % cmd)

def tget(cmd):
   proc = Popen("tmux %s" % cmd, stdout=PIPE, stderr=PIPE, shell=True)
   out, err = proc.communicate()
   exitcode = proc.returncode
   return out

def splitWindow():
   global totalWindows
   global MAX_WINDOWS
   if totalWindows < MAX_WINDOWS:
       tcmd("split-window -d -h")
       totalWindows += 1

def newWindow():
   global totalWindows
   global MAX_WINDOWS
   if totalWindows < MAX_WINDOWS:
       tcmd("new-window")
       totalWindows += 1

def getCurrentWindow():
   return int(tget("display-message -p '#I'"))

def getCurrentPane():
   return int(tget("display-message -p '#P'"))

def carvePanes(numPerWindow, layout):
   for i in range(numPerWindow - 1):
       splitWindow()
       tcmd("select-layout %s" % layout)
   tcmd("select-layout %s" % layout)
   return getCurrentWindow()

def digestCommands(commands):
   # Remove comments and empty lines before joining lines.
   # Comments are lines that start with # but not #smux.
   rawCommands = [x for x in commands if x != '' and (x.startswith("#smux ") or not x.startswith("#"))]
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
   if bufferedLine: digestedCommands.append(bufferedLine)
   return digestedCommands

def sendCommand(cmd, pane = 0, window = None, ex = True):
   def quoteKey(key):
       return f'"{key}"' if key == "'" else f"'{key}'"
   # Deal with single quotes inside command by spliting the command by single
   # quotes, wrapping the single quotes in double quotes, and wrapping the
   # other parts in single quotes.
   def prepareCommand(cmd):
       if not "'" in cmd: return f"'{cmd}'"
       return '"\'"'.join(f"'{x}'" for x in cmd.split("'"))

   time.sleep(0.1)
   if not window: window = getCurrentWindow()
   # If the command is a directive to smux itself, then do not pass it through.
   if cmd.startswith("#smux "):
       # Skip the initial command
       args = shlex.split(cmd)[1:]
       if args[0] == 'paste-buffer':
           tcmd(f"paste-buffer -t ':{window}.{pane}' " + shlex.join(args[1:]))
       elif args[0] == 'send-keys':
           # This option is useful for sending something like "Enter" with
           # semantic meaning, rather than literally. This is needed rather
           # than just allowing the script to directly invoke `tmux send-keys`
           # because the target pane may be runnig a completely different
           # process which we want to feed special input to (e.g. it is waiting
           # for the user to type a special key such as Enter).
           tcmd(f"send-keys -t ':{window}.{pane}' " + shlex.join(args[1:]))
       elif args[0] == 'sleep':
           time.sleep(float(args[1]))
       elif args[0] == 'shell':
            # Use the suffix of the original string, because
            # shlex.join(shlex.split(X))  turns double-quotes into
            # single-quotes, which is undesirable for expading variables.
            fullCommand = f'export window={window}; export pane={pane}; ' + cmd[cmd.index("shell") + len("shell"):]
            os.system(fullCommand)
       return
   # We must send commands one character to avoid weird quote treatment by the
   # sell when invoking send-keys.
   if ex:
       tcmd(f"send-keys -t {window}.{pane} -l " + prepareCommand(cmd))
       tcmd(f"send-keys -t {window}.{pane} Enter")
   else:
       tcmd(f"send-keys -t {window}.{pane} -l " + prepareCommand(cmd))

def create(numPanesPerWindow, commands, layout = 'tiled', executeAfterCreate = None, noCreate = False):
   """
   Create a set of tmux panes and run each command list in commands in its own pane.

   Parameters
   ----------
   numPanesPerWindow: int
     The number of panes to create in each window. If there are more lists of
     commands than numPanesPerWindow, more windows will be created.
   Commands : list(list(str))
     A list of command lists. Each command list will be send to a given pane.
   executeBeforeAttach : Callable[[], None]
     A function that a client can pass in to be executed after creating the
     windows. For example, one can synchronize the panes by passing the following:
     lambda : smux.tcmd("setw synchronize-panes on")
   noCreate : bool
     True means smux should send the commands to the pane that the caller lives
     in, rather than creating new panes. Ignored if more than one command list
     is given, or caller is not currently running in a tmux session.
     This can be useful for using smux to ssh into a machine and then run
     commands inside the ssh session.
   """
   # Remove comments in commands and join together line-continuations for #smux
   # commands.
   for i in range(len(commands)):
       commands[i] = digestCommands(commands[i])

   if not numPanesPerWindow  > 0:
       print("No panes specified.")
       return
   if numPanesPerWindow > 30:
       print("Number per window must be less than 30!")
       return
   tmux = os.environ.get('TMUX')
   if noCreate and (not tmux or len(commands) != 1):
       print("noCreate parameter ignored because we are not in a tmux session or len(commands) != 1")
   if not tmux:
       tcmd("new-session -d")
   elif noCreate and len(commands) == 1:
       # Run ourselves in a subshell, so that Python does not consume the input
       # intended for the new foreground processes started by the script.
       if not os.environ.get('SMUX_SUBSHELL'):
           os.system(f'SMUX_SUBSHELL=1 {shlex.join(sys.argv)}  & > /dev/null 2>&1')
           return

       # Target the current window that invoked this command.
       currentWindow = getCurrentWindow()
       currentPane = getCurrentPane()
       for x in commands[0]:
          sendCommand(x, currentPane, currentWindow)
       return
   else:
       newWindow()

   panesNeeded = len(commands)
   index = 0
   while panesNeeded > 0:
      windowNum = carvePanes(numPanesPerWindow, layout)
      panesNeeded -= numPanesPerWindow

      # Send the commands in with CR
      for i in range(min(numPanesPerWindow, len(commands))):
         print(i)
         for x in commands[i]:
            sendCommand(x,i, windowNum)

      # Pop off the commands we just finished with
      for i in range(min(numPanesPerWindow, len(commands))):
         commands.pop(0)

      # Create a new window if necessary
      if panesNeeded > 0:
        newWindow()

   if executeAfterCreate: executeAfterCreate()
   if not tmux:
      tcmd("attach-session")


def startSession(file):
  cmds = []

  # default args in place
  args = {"PANES_PER_WINDOW" : "4", "LAYOUT" : "tiled", "NO_CREATE" : False}
  cur_cmds = None
  for line in file:
    line = line.strip()
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
           else:
             left,right = line.split('=',1)
             args[left.strip()] = right.strip()
       except:
           print("Argment '%s' ignored" % line)
           print("Arguments must be in the form of key = value")
           continue

    else: # Actual session is being added to
       cur_cmds.append(line.strip())

  if cur_cmds:
    cmds.append(cur_cmds)
  # Start the sessions
  create(int(args['PANES_PER_WINDOW']), cmds, args['LAYOUT'], noCreate = args['NO_CREATE'])

def usage():
   doc_string = '''
   smux.py <session_spec_file>

   The format of session_spec_file consists of ini-style parameters followed by
   lists of commands delimited by lines beginning with '---'.

   Any line starting with a # is considered a comment and ignored.

   Currently there are three supported parameters.

   PANES_PER_WINDOW,
       The number of panes that each window will be carved into.

   LAYOUT,
       One of the five standard tmux layouts, given below.
       even-horizontal, even-vertical, main-horizontal, main-vertical, tiled.

   NO_CREATE,
       When given (no parameter value), smux will attempt to send the commands
       to the caller's window. Option is ignored if more than one command
       sequence if given, or caller is not inside a tmux session.

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

   '''
   print(doc_string)
   sys.exit(1)

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ['--help', '-h','-?'] : usage()
    try:
      with open(sys.argv[1]) as f:
        startSession(f)
    except:
      traceback.print_exc()
      print('File "%s" does not exist.' % sys.argv[1], file=sys.stderr)
      sys.exit(2)

if __name__ == "__main__": main()
