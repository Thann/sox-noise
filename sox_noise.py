#!/usr/bin/env python
# Noise generator GUI powered by SoX
# fair-used off of: https://gist.github.com/rsvp/1209835

import os
import gi
import sys
import signal
import argparse
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk
from subprocess import Popen


class SoxNoise:
    def __init__(self, args=[]):
        builder = Gtk.Builder()
        builder.add_from_file(os.path.join(os.path.dirname(__file__), "main.ui"))
        builder.connect_signals(self)
        self.window = builder.get_object("main-window")

        self.subp = None
        self.play_button = builder.get_object('play-button')
        self.band_center = builder.get_object('adj-band-center')
        self.band_width = builder.get_object('adj-band-width')
        self.trem_speed = builder.get_object('adj-tremolo-speed')
        self.trem_depth = builder.get_object('adj-tremolo-depth')
        self.reverb = builder.get_object('adj-reverb')
        self.volume = builder.get_object('adj-volume')

        # parse args
        parser = argparse.ArgumentParser(description='Noise Generator powered by SoX.', prog=__file__)
        parser.add_argument('noise', choices=['brown', 'pink', 'white', 'tpdf'],
            nargs='?', default='brown', help='The "color" of noise')
        parser.add_argument('--play',          action='store_true',   help='Start playing on open')
        parser.add_argument('--volume',        type=int, default=80,  help='[1-100]')
        parser.add_argument('--band-center',   type=int, default=500, help='Band-pass filter around center frequency [1-2000] (Hz) ')
        parser.add_argument('--band-width',    type=int, default=500, help='Band-pass filter width [1-1000]')
        parser.add_argument('--effects',       action='store_true',   help='Show effects options')
        parser.add_argument('--reverb',        type=int, default=20,  help='Small amounts make it sound more natural [0-100]')
        parser.add_argument('--tremolo-speed', type=int, default=2,   help='Periodically raise and lower the volume [0-10] (cycles per duration)')
        parser.add_argument('--tremolo-depth', type=int, default=30,  help='Tremolo intensity [0-100]')
        parser.add_argument('--duration',      type=int, default=60,  help='How many seconds to generate noise before looping')
        parser.add_argument('--tray',          action='store_true',   help='Show an icon in the system tray')
        parser.add_argument('--hide',          action='store_true',   help="Don't show the window")
        pargs = parser.parse_args(args[1:])

        builder.get_object(f'btn-noise-{pargs.noise}').emit('clicked')
        self.band_center.set_value(pargs.band_center)
        self.band_width.set_value(pargs.band_width)
        self.trem_speed.set_value(pargs.tremolo_speed) # millihertz
        self.trem_depth.set_value(pargs.tremolo_depth)
        self.reverb.set_value(pargs.reverb)
        self.volume.set_value(pargs.volume)
        self.duration = pargs.duration
        self.noise = pargs.noise
        self.needs_update = False

        # Apply styles - Hack to align the tremolo-speed scale
        css = b'.lpad { margin-left: 1.1ex; }'
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(css)
        Gtk.StyleContext().add_provider_for_screen(Gdk.Screen.get_default(),
            css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        if pargs.effects:
            builder.get_object('effects-expander').set_expanded(True)
        if not pargs.hide:
            self.window.show_all()
        if pargs.hide or pargs.play:
            self.play_button.set_active(True)
        if pargs.tray:
            try:
                gi.require_version('AppIndicator3', '0.1')
                from gi.repository import AppIndicator3
                self.ind = AppIndicator3.Indicator.new('sox-noise', 'audio-volume-high',
                    AppIndicator3.IndicatorCategory.APPLICATION_STATUS)
                self.ind.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
                menu = Gtk.Menu()  # Hack: indicator needs menu, but we dont want one
                menu.connect('draw', lambda a,b: (menu.hide(), self.window.present()))
                self.ind.set_menu(menu)
            except Exception as e:
                print('TRAY ERROR:', e)

    def onDestroy(self, *args):
        if self.subp:
            self.subp.kill()
        Gtk.main_quit()

    def setNoise(self, button):
        if (button.get_active()):
            self.noise = button.get_label().lower()
        self.play()  # resume playback

    def valueChanged(self, adj):
        # slider changed
        self.needs_update = True

    def doneAdjusting(self, widget=None, event=None):
        # resume playback with new settings
        if self.needs_update and self.subp:
            self.needs_update = False
            self.play()

    def play(self, button=None):
        if self.subp:
            self.subp.kill()

        # make tspeed a fraction of the duration
        tspeed = int(self.trem_speed.get_value())/self.duration

        if self.play_button.get_active():
            args = ['sox', '-c2', '--null', '-talsa', 'synth', f'0:{self.duration}',
                f'{self.noise}noise',
                'band', '-n', str(self.band_center.get_value()), str(self.band_width.get_value()),
                'tremolo', str(tspeed), str(self.trem_depth.get_value()),
                'reverb', str(self.reverb.get_value()),
                'vol', str(self.volume.get_value()/100),
                # 'bass', '-11', 'treble' '-1',
                # fade: prevents pops/clicks at the end of an iteration
                'fade', 'q', '.005', f'0:{self.duration}', '.005',
                'repeat', '-']
            print('\n ===>', ' '.join(args))
            self.subp = Popen(args)


def start():
    win = SoxNoise(sys.argv)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, win.onDestroy)
    Gtk.main()

if __name__ == "__main__":
    start()
