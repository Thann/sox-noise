#!/usr/bin/env python
# Noise generator GUI powered by SoX
# fair-used off of: https://gist.github.com/rsvp/1209835

import gi
import sys
import signal
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
from subprocess import Popen


class SoxNoise:
    def __init__(self, args=[]):
        builder = Gtk.Builder()
        builder.add_from_file("sox-noise.ui")
        builder.connect_signals(self)
        self.window = builder.get_object("main-window")
        self.window.show_all()

        self.subp = None
        self.duration = '01:00'
        self.play_button = builder.get_object('play-button')
        self.band_center = builder.get_object('adj-band-center')
        self.band_width = builder.get_object('adj-band-width')
        self.trem_speed = builder.get_object('adj-tremolo-speed')
        self.trem_depth = builder.get_object('adj-tremolo-depth')
        self.reverb = builder.get_object('adj-reverb')
        self.volume = builder.get_object('adj-volume')

        # set defaults
        builder.get_object('btn-noise-brown').emit('toggled')
        self.band_center.set_value(500)
        self.band_width.set_value(500)
        self.trem_speed.set_value(33.333) # millihertz
        self.trem_depth.set_value(43)
        self.reverb.set_value(19)
        self.volume.set_value(80)
        auto_play = False

        # parse args
        for arg in args[1:]:
            try:
                a = arg.lstrip('-').split('=')
                if a[0] == 'play':
                    auto_play = True
                elif a[0] == 'advanced':
                    builder.get_object('advanced-expander').set_expanded(True)
                elif a[0] == 'noise':
                    builder.get_object(f'btn-noise-{a[1].lower()}').emit('clicked')
                else:
                    builder.get_object(f'adj-{a[0].lower()}').set_value(float(a[1]))
            except Exception as e:
                print('ARG ERROR:', arg, '::', e)

        self.needs_update = False
        if auto_play:
            self.play_button.set_active(True)
            self.play()

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
