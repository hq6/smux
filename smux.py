#!/usr/bin/python

# Copyright (c) 2014 Henry Qin
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

totalWindows = 0
MAX_WINDOWS=500

def tcmd(cmd):
   os.system("tmux %s" % cmd)

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
   
   
def carvePanes(numPerWindow, layout):
   for i in xrange(numPerWindow - 1):
       splitWindow()
   tcmd("select-layout %s" % layout)
    
      
def sendCommand(cmd, pane = 0, ex = True):
   time.sleep(0.1) 
   if ex:
       tcmd("send-keys -t %d '%s ' Enter" % (pane,cmd))
   else:
       tcmd("send-keys -t %d '%s'" % (pane,cmd))
   

# Commands is a list of lists, where each list is a sequence of
# commands to give to particular window.
def create(numPanesPerWindow, commands, layout = 'tiled'):
   # Defend against forkbombs
   if not numPanesPerWindow  > 0: 
       print "Forkbomb attempt detected!"
       return
   if numPanesPerWindow > 30:
       print "Number per window must be less than 30!"
       return
   tmux = True
   if not os.environ.get('TMUX'): # Session exist
       tcmd("new-session -d")
       tmux = False
   else:
       newWindow()
   
   panesNeeded = len(commands)
   index = 0
   while panesNeeded > 0:
      carvePanes(numPanesPerWindow, layout)
      panesNeeded -= numPanesPerWindow
      
      # Send the commands in with CR
      for i in xrange(min(numPanesPerWindow, len(commands))): 
         print i 
         for x in commands[i]:
            sendCommand(x,i)

      # Pop off the commands we just finished with
      for i in xrange(min(numPanesPerWindow, len(commands))): 
         commands.pop(0)

      # Create a new window if necessary
      if panesNeeded > 0:
        newWindow()

   if not tmux:
      tcmd("attach-session")
   

def startSession(file):
  cmds = []

  # default args in place
  args = {"PANES_PER_WINDOW" : "4", "LAYOUT" : "tiled"}
  cur_cmds = None
  for line in file: 
    line = line.strip()
    # comments
    if line == '' or line.startswith("#"): continue
    # Start a new pane specification
    if line.startswith("---"):
       if cur_cmds is not None:
          cmds.append(cur_cmds)
       cur_cmds = []
       continue
    # Configuration part
    if cur_cmds == None:
       try:
           left,right = line.split('=',1)
           args[left.strip()] = right.strip()
       except:
           print "Argment '%s' ignored" % line
           print "Arguments must be in the form of key = value"
           continue

    else: # Actual session is being added to
       cur_cmds.append(line.strip())
      
  if cur_cmds:
    cmds.append(cur_cmds)
  # Start the sessions
  create(int(args['PANES_PER_WINDOW']), cmds, args['LAYOUT'])
      
def usage():
   doc_string = '''
   mux.py <session_spec_file>

   The format of session_spec_file consists of ini-style parameters followed by
   lists of commands delimited by lines beginning with '---'.  

   Any line starting with a # is considered a comment and ignored.

   Currently there are two supported parameters.
   
   PANES_PER_WINDOW, 
       The number of panes that each window will be carved into

   LAYOUT, 
       One of the five standard tmux layouts, given below.
       even-horizontal, even-vertical, main-horizontal, main-vertical, tiled.

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
   print doc_string
   sys.exit(1)

def main():
    if len(sys.argv) < 2: usage()
    with open(sys.argv[1]) as f:
      startSession(f)
        
if __name__ == "__main__": main()
