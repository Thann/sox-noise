#!/usr/bin/env python
# Noise generator GUI powered by SoX
# fair-used off of: https://gist.github.com/rsvp/1209835

import gi
import sys
import signal
import argparse
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
from subprocess import Popen


class SoxNoise:
    def __init__(self, args=[]):
        builder = Gtk.Builder()
        builder.add_from_file("sox-noise.ui")
        builder.connect_signals(self)
        self.window = builder.get_object("main-window")

        self.subp = None
        self.duration = '01:00'
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
        parser.add_argument('--play',          action='store_true',     help='Start playing on open')
        parser.add_argument('--volume',        type=float, default=80,  help='[1-100]')
        parser.add_argument('--band-center',   type=float, default=500, help='Band-pass filter around center frequency [1-2000] (Hz) ')
        parser.add_argument('--band-width',    type=float, default=500, help='Band-pass filter width [1-1000]')
        parser.add_argument('--advanced',      action='store_true',     help='Show advanced options')
        parser.add_argument('--tremolo-speed', type=float, default=33,  help='Periodically raise and lower the volume [1-100] (mHz) ')
        parser.add_argument('--tremolo-depth', type=float, default=43,  help='Tremolo intensity[1-100]')
        parser.add_argument('--reverb',        type=float, default=19,  help='Small amounts make it sound more natural [1-100]')
        parser.add_argument('--hide',          action='store_true',     help="Don't show the window")
        pargs = parser.parse_args(args[1:])

        builder.get_object(f'btn-noise-{pargs.noise}').emit('clicked')
        self.band_center.set_value(pargs.band_center)
        self.band_width.set_value(pargs.band_width)
        self.trem_speed.set_value(pargs.tremolo_speed) # millihertz
        self.trem_depth.set_value(pargs.tremolo_depth)
        self.reverb.set_value(pargs.reverb)
        self.volume.set_value(pargs.volume)
        self.noise = pargs.noise
        self.needs_update = False

        if pargs.advanced:
            builder.get_object('advanced-expander').set_expanded(True)
        if not pargs.hide:
            self.window.show_all()
        if pargs.hide or pargs.play:
            self.play_button.set_active(True)

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
        if self.play_button.get_active():
            args = ['play', '-c2', '--null', '-talsa', 'synth', self.duration,
                f'{self.noise}noise',
                'band', '-n', str(self.band_center.get_value()), str(self.band_width.get_value()),
                'tremolo', str(self.trem_speed.get_value()/1000), str(self.trem_depth.get_value()),
                'reverb', str(self.reverb.get_value()),
                'vol', str(self.volume.get_value()/100),
                # 'bass', '-11', 'treble' '-1',
                # fade: prevents pops/clicks at the end of an iteration
                'fade', 'q', '.01', self.duration, '.01',
                'repeat', '99999']
            print('\n', args)
            self.subp = Popen(args)


if __name__ == "__main__":
    win = SoxNoise(sys.argv)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, win.onDestroy)
    Gtk.main()
