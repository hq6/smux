# smux

The minimal tmux launcher, with the fewest options to set and the fastest
ramp-up time.

## Dependencies

 - Python2
 - tmux (any version)

## Installation

    git clone https://github.com/hq6/smux.git
    # Add the directory to your PATH

## Usage (as a command line tool)
   
   0. Create a new file, either from scratch or by copying Sample.smux.
   1. (Optional) Specify PANES_PER_WINDOW and LAYOUT as described in the usage message.
   2. For every pane you want to launch, write an entry of the following form.

         ---------
         command1
         command2
         command3

      Note that a pane does not necessary need to run any commands.
   3. smux.py <input_file_name>

## Usage (as a library)


    import smux

    smux.create(numPerWindow,
            [["command1_for_pane1", "command2_for_pane1"],
             ["command1_for_pane2", "command2_for_pane2"],
             ...
             ])
