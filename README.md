# smux

The minimal tmux launcher, with the fewest options to set and the fastest
ramp-up time. This project is on [Github](https://github.com/hq6/smux)  and on [PyPi](https://pypi.org/project/smux.py/) (this README is shared).

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
[documentation](https://github.com/hq6/smux/blob/master/smux.txt#L38) for details.

See the [samples](https://github.com/hq6/smux/tree/master/samples) directory for example smux scripts.

## Why write another tmux launcher?

tmuxp and tmuxinator are powerful tmux session management systems that already
exist, so why create another one?  The big reasons are the ergonomics and ease
of learning that arises from a flat input file format and extremely few options.

Consider smux if one of the following is true of your use case:

1. You want to write commands exactly the same way you write a bash script. You
   just want your commands to execute in different tmux panes. You have neither
   time nor desire to learn a custom input format and understand a large number
   of options.
2. You do not care about "managing" sessions, and just want to automate
   pane creation.
3. You want scripts that you can directly copy-and-paste commands out of when
   you need to run commands manually.
4. You want to leverage #smux directives for convenient access to tmux
   buffers and waiting for input.
5. You want to embed a tmux launcher into another Python script that generate
   commands to run, without having to fit those other scripts into someone
   else's framework. This can be done with a single call to `smux.create`.

## Demo (Click to View)
Writing and running a simple smux script in under 60 seconds.

[![asciicast](https://asciinema.org/a/381955.svg)](https://asciinema.org/a/381955)

Expect-like features with #smux directives, such as waiting for input before
sending specific keystrokes.

[![asciicast](https://asciinema.org/a/381956.svg)](https://asciinema.org/a/381956)


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
