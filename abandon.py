#!/usr/bin/env python
# vim: set expandtab tabstop=4 shiftwidth=4:

# Copyright (c) 2019, CJ Kucera
# All rights reserved.
#   
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the development team nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL CJ KUCERA BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import os
import sys
import urwid
import subprocess

class InfoFile(object):

    # Supported game types
    valid_types = set([
        # DOS
        'dos', 'dosbox',

        # NES
        'nes', 'fceux',

        # SNES
        'snes', 'snes9x-gtk',

        # VBA
        'vba', 'visualboyadvance-m',

        # Z-Machine
        'zmachine', 'frotz', 'grotz',
        ])

    # Types which require a 'rom' line
    require_rom = set([
        'nes', 'fceux',
        'snes', 'snes9x-gtk',
        'vba', 'visualboyadvance-m',
        'zmachine', 'frotz', 'grotz',
        ])

    # Type translations, basically allowing us to default to a specific
    # emulator but allowing an info file to specify one manually (for
    # instances where my "default" emulator for a game type doesn't work
    # as well as an alternative)
    type_trans = {
            'dos': 'dosbox',
            'nes': 'fceux',
            'snes': 'snes9x-gtk',
            'vba': 'visualboyadvance-m',
            'zmachine': 'frotz',
            }

    def __init__(self, filename):
        self.filename = filename
        self.base_dir = os.path.dirname(self.filename)
        self.sort = None
        self.name = None
        self.category = False
        self.type = None
        self.rom = None
        with open(filename) as df:
            for line in [l.strip() for l in df.readlines()]:
                if ': ' in line:
                    (first, second) = line.split(': ', 1)
                    first = first.lower().strip()
                    second = second.strip()
                    if first == 'cat':
                        self.category = True
                        self.name = second
                    elif first == 'type':
                        self.type = second
                    elif first == 'name':
                        self.category = False
                        self.name = second
                    elif first == 'sort':
                        self.sort = second.lower()
                    elif first == 'rom':
                        self.rom = second
                    else:
                        raise Exception('Unknown info file key: {}'.format(first))
                elif line != '':
                    raise Exception('Unknown line: {}'.format(line))
        if self.sort is None:
            self.sort = self.name.lower()
        if not self.category:
            if self.type:
                if self.type not in self.valid_types:
                    raise Exception('type must be one of: {}'.format(', '.join(sorted(self.valid_types))))
            else:
                raise Exception('type was not specified')
        if self.type in self.require_rom and not self.rom:
            raise Exception('does not specify a ROM file')
        if self.rom:
            self.full_rom = os.path.join(self.base_dir, self.rom)
            if not os.path.exists(self.full_rom):
                raise Exception('{} does not exist'.format(self.rom))

    def __lt__(self, other):
        return self.sort < other.sort

    def __repr__(self):
        return 'InfoFile({})'.format(self.name)

    def activate(self):
        if self.category:
            return

        if self.type in self.type_trans:
            real_type = self.type_trans[self.type]
        else:
            real_type = self.type

        # Save our current dir, and go into the game's dir.
        # This is probably not actually needed, given that
        # we're using `cwd` in our `subprocess.run` call,
        # but ehhh.
        current_dir = os.getcwd()
        os.chdir(self.base_dir)

        cmdline = []
        if real_type == 'dosbox':

            cfg_name = os.path.join(self.base_dir, 'abandon.conf')
            if not os.path.exists(cfg_name):
                cfg_name = os.path.expanduser('~/.dosbox/dosbox.conf')

            cmdline = [
                    'dosbox',
                    '-c', 'mount c "{}"'.format(self.base_dir),
                    '-c', 'c:',
                    '-c', 'echo Using {}'.format(cfg_name),
                    '-conf', cfg_name,
                    ]

            if self.rom:
                cmdline.extend(['-c', self.rom])

        elif real_type == 'fceux':

            cmdline = [
                    'fceux',
                    self.full_rom,
                    ]

        elif real_type == 'snes9x-gtk':

            cmdline = [
                    'snes9x-gtk',
                    self.full_rom,
                    ]

        elif real_type == 'visualboyadvance-m':

            cmdline = [
                    'visualboyadvance-m',
                    self.full_rom,
                    ]

        elif real_type == 'frotz':

            cmdline = [
                    'uxterm',
                    '-geometry', '120x50',
                    '-e',
                    # We need to change directory even despite our chdir
                    # above, and our `cwd` option below, since the terminal
                    # will otherwise start off in my homedir.
                    'cd "{}"; frotz "{}"'.format(self.base_dir, self.rom),
                    ]

        elif real_type == 'grotz':

            cmdline = [
                    'grotz', self.full_rom,
                    ]

        lines = []
        if len(cmdline) > 0:
            cp = subprocess.run(cmdline,
                    capture_output=True,
                    text=True,
                    cwd=self.base_dir,
                    )
            if len(cp.stdout) > 0:
                lines.extend(['Output:', ''])
                lines.extend(cp.stdout.splitlines())
                if len(cp.stderr) > 0:
                    lines.append('')
            if len(cp.stderr) > 0:
                lines.extend(['', 'Errors:', ''])
                lines.extend(cp.stderr.splitlines())
            if cp.returncode != 0 and len(lines) == 0:
                lines.append('The program did not complete successfully but no output was captured.')

        # Make sure to hop back to our previous dir
        os.chdir(current_dir)

        return lines

class SimplePopUp(urwid.WidgetWrap):

    def __init__(self, label):
        box = urwid.LineBox(urwid.Pile([urwid.Text(label)]))
        fill = urwid.Filler(box)
        super().__init__(fill)

class MultiPopUp(urwid.WidgetWrap):

    signals = ['close']

    def __init__(self, lines):

        widgets = [urwid.Text(l) for l in lines]
        widgets.append(urwid.Text(''))
        button = urwid.Button('OK')
        urwid.connect_signal(button, 'click', self.close)
        widgets.append(urwid.AttrMap(button, 'button_std', focus_map='button_std_selected'))
        walker = urwid.SimpleFocusListWalker(widgets)
        listbox = urwid.ListBox(walker)
        box = urwid.LineBox(listbox)
        super().__init__(box)

    def close(self, button):
        self._emit('close')

class AppPopUpLauncher(urwid.PopUpLauncher):

    width_pct_simple = 80
    height_pct_simple = 15
    width_pct_multi = 90
    height_pct_multi = 90
    min_cols = 60
    min_rows = 5

    (T_SIMPLE,
        T_MULTI) = range(2)

    def __init__(self, screen, widget):
        super().__init__(widget)
        self.screen = screen
        self.popup_text = ''
        self.popup_lines = []
        self.popup_type = AppPopUpLauncher.T_SIMPLE
        self.width_pct = self.width_pct_simple
        self.height_pct = self.height_pct_simple

    def open_simple_pop_up(self, text):
        self.popup_text = text
        self.popup_type = AppPopUpLauncher.T_SIMPLE
        self.width_pct = self.width_pct_simple
        self.height_pct = self.height_pct_simple
        self.open_pop_up()

    def open_multi_pop_up(self, lines):
        self.popup_lines = lines
        self.popup_type = AppPopUpLauncher.T_MULTI
        self.width_pct = self.width_pct_multi
        self.height_pct = self.height_pct_multi
        self.open_pop_up()

    def create_pop_up(self):
        if self.popup_type == AppPopUpLauncher.T_SIMPLE:
            return SimplePopUp(self.popup_text)
        else:
            pop_up = MultiPopUp(self.popup_lines)
            urwid.connect_signal(pop_up, 'close', lambda b: self.close_pop_up())
            return pop_up

    def get_pop_up_parameters(self):
        screen_cols, screen_rows = self.screen.get_cols_rows()
        screen_cols -= 2
        screen_rows -= 2

        width = int(screen_cols*self.width_pct/100)
        height = int(screen_rows*self.height_pct/100)
        width = max(width, self.min_cols)
        height = max(height, self.min_rows)
        width = min(width, screen_cols)
        height = min(height, screen_rows)

        padding_x = max(int((screen_cols - width) / 2), 0)
        padding_y = max(int((screen_rows - height) / 2), 0)

        return {
                'left': padding_x,
                'top': padding_y,
                'overlay_width': width,
                'overlay_height': height,
                }

class App(object):

    def __init__(self, base_dir):

        self.cur_dir = base_dir

        self.breadcrumbs = ['[Abandonware]']

        self.items = []
        self.errors = []
        self.action_walker = urwid.SimpleFocusListWalker([])
        self.action_listbox = urwid.ListBox(self.action_walker)
        self.popup_launcher = AppPopUpLauncher(urwid.raw_display.Screen(), self.action_listbox)
        self.container = urwid.LineBox(self.popup_launcher, 'main_box')

        self.main_frame = urwid.Frame(self.container)
        palette = [
                ('main_box', 'white', 'black'),
                ('button_game', 'light green', 'black'),
                ('button_game_selected', 'black', 'dark green'),
                ('button_cat', 'yellow', 'black'),
                ('button_cat_selected', 'black', 'brown'),
                ('button_std', 'white', 'black'),
                ('button_std_selected', 'black', 'dark gray'),
                ('button_error', 'light red', 'black'),
                ('button_error_selected', 'black', 'dark red'),
                (None, 'white', 'black'),
                ]
        self.loop = urwid.MainLoop(self.main_frame, palette,
                pop_ups=True, unhandled_input=self.key_handler)
        self.read_cur_dir()

    def update_display(self, prev_dir=None):

        # Update Header
        self.container.set_title(' > '.join(self.breadcrumbs))

        # Get rid of old entries
        for button in list(self.action_walker):
            self.action_walker.remove(button)

        # Add valid cats/games
        for idx, item in enumerate(sorted(self.items)):
            if item.category:
                color = 'button_cat'
                color_select = 'button_cat_selected'
            else:
                color = 'button_game'
                color_select = 'button_game_selected'
            button = urwid.Button(item.name)
            urwid.connect_signal(button, 'click', self.click_item, item)
            self.action_walker.append(urwid.AttrMap(button, color, focus_map=color_select))
            if prev_dir and item.base_dir == prev_dir:
                self.action_walker.set_focus(idx)

        # Add errors
        for (dirname, error) in self.errors:
            button = urwid.Button('Error in {}: {}'.format(dirname, str(error)))
            self.action_walker.append(urwid.AttrMap(button, 'button_error', focus_map='button_error_selected'))

        # Add "back" if we have one
        if len(self.breadcrumbs) > 1:
            button = urwid.Button('Back...')
            urwid.connect_signal(button, 'click', self.back)
            self.action_walker.append(urwid.AttrMap(button, 'button_std', focus_map='button_std_selected'))

        # Add "quit"
        button = urwid.Button('Quit...')
        urwid.connect_signal(button, 'click', self.exit_main_loop)
        self.action_walker.append(urwid.AttrMap(button, 'button_std', focus_map='button_std_selected'))

    def read_cur_dir(self, prev_dir=None):

        filenames = sorted(os.listdir(self.cur_dir))
        self.items = []
        self.errors = []
        for filename in filenames:
            if filename[0] == '.':
                continue
            dir_name = os.path.join(self.cur_dir, filename)
            if os.path.isdir(dir_name):
                filename_info = os.path.join(dir_name, 'abandon.info')
                if os.path.exists(filename_info):
                    try:
                        self.items.append(InfoFile(filename_info))
                    except Exception as e:
                        self.errors.append((filename, e))

        self.update_display(prev_dir)

    def run(self):

        self.loop.run()

    def exit_main_loop(self, button):

        raise urwid.ExitMainLoop()

    def click_item(self, button, item):

        if item.category:
            self.breadcrumbs.append(item.name)
            self.cur_dir = item.base_dir
            self.read_cur_dir()
        else:
            self.popup_launcher.open_simple_pop_up('Running {}'.format(item.name))
            self.loop.draw_screen()
            lines = item.activate()
            self.popup_launcher.close_pop_up()

            if len(lines) > 0:
                self.popup_launcher.open_multi_pop_up(lines)

    def back(self, button):

        if len(self.breadcrumbs) > 1:
            self.breadcrumbs.pop()
            old_dir = self.cur_dir
            self.cur_dir = os.path.dirname(self.cur_dir)
            self.read_cur_dir(old_dir)

    def key_handler(self, key):
        if key == 'down':
            self.action_walker.set_focus(0)
        elif key == 'up':
            self.action_walker.set_focus(len(self.action_walker)-1)
        elif key == 'b':
            self.back(None)
        elif key == 'q':
            raise urwid.ExitMainLoop()

if __name__ == '__main__':
    base_dir = '/usr/local/games/abandon'
    app = App(base_dir)
    app.run()
