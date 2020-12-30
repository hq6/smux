# smux

The minimal tmux launcher, with the fewest options to set and the fastest
ramp-up time.

Originally created as a tool to make it easier to reproduce (and interactively
debug) distributed systems bugs that required sshing into a lot of servers and
starting processes, smux is a general purpose tmux launcher whose input
resembles in all respects a concatenation of bash scripts to be run on each
terminal.

In addition to being able to send literal commands to tmux windows, `smux`
offers a variety of special `#smux` directives useable in its input files that
make it easy to do certain `expect`-esque tasks inside tmux, such as waiting
for prompts, pasting buffers, and executing arbitrary shell commmands
internally (for example, to wait for user input before proceeding to send more
commands to various panes). See `#smux directives` in the
[documentation](https://github.com/hq6/smux/blob/master/smux.txt#L146) for details.

## Dependencies

 - Python 3.8+
 - tmux (any version)

## Installation

Manual Method:

    git clone https://github.com/hq6/smux.git
    # Add the directory to your PATH

Automatic Method:

    pip3 install smux.py

## Usage (as a command line tool)

   0. Create a new file, either from scratch or by copying Sample.smux.
   1. (Optional) Specify desired options described in `help(smux)`.
   2. For every pane you want to launch, write an entry of the following form.
         ```
         ---------
         command1
         command2
         command3
         ```

      Note that a pane does not necessary need to run any commands.

      Note further that it is not uncommon for the first command in a pane to
      be `ssh ...` and then the subsequent commands the ones to be run on the
      rmeote server.

   3. smux.py <input_file_name>

## Usage (as a library)


    import smux

    smux.create(numPerWindow,
            [["command1_for_pane1", "command2_for_pane1"],
             ["command1_for_pane2", "command2_for_pane2"],
             ...
             ])
