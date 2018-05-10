from setuptools import setup

long_description=\
"""
smux
====================

The minimal tmux launcher, with the fewest options to set and the fastest
ramp-up time.

Originally created to be tool to make it easier to reproduce (and interactively
debug) distributed systems bugs that required sshing into a lot of servers and
starting processes, smux is a general purpose tmux launcher whose input
resembles in all respects a concatenation of bash scripts to be run on each
terminal.

Dependencies
========================================

* Python2
* tmux (any version)

Installation
========================================

Run the following command::

    sudo pip install smux

Usage (as a command line tool)
========================================

0. Create a new file, either from scratch or by copying Sample.smux_.
1. (Optional) Specify ``PANES_PER_WINDOW`` and ``LAYOUT`` as described in the
   usage message.
2. For every pane you want to launch, write an entry of the following form.::

      ---------
      command1
      command2
      command3

   Note that a pane does not necessary need to run any commands.

   Note further that it is not uncommon for the first command in a pane to
   be ``ssh ...`` and then the subsequent commands the ones to be run on the
   rmeote server.

3. ``smux.py <input_file_name>``

Usage (as a library)
========================================

smux has a single API call ``create``::

    import smux

    smux.create(numPerWindow,
            [["command1_for_pane1", "command2_for_pane1"],
             ["command1_for_pane2", "command2_for_pane2"],
             ...
             ])

.. _Sample.smux: https://github.com/hq6/smux/blob/master/Sample.smux
"""

setup(
  name="smux",
  version='0.6',
  scripts=['smux.py'],
  author="Henry Qin",
  author_email="root@hq6.me",
  description="Simple tmux launcher that will take less than 2 minutes to learn and should work across all versions of tmux",
  long_description=long_description,
  platforms=["All platforms that tmux runs on."],
  license="MIT",
  url="https://github.com/hq6/smux"
)
