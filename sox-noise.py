#!/usr/bin/env python
# Noise generator GUI based off of https://gist.github.com/rsvp/1209835
# requires: SoX

import gi
import sys
import signal
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
from subprocess import Popen


class SoxNoise:
    def __init__(self, args):
        builder = Gtk.Builder()
        builder.add_from_file("sox-noise.ui")
        builder.connect_signals(self)
        self.window = builder.get_object("main-window")
        self.window.show_all()

        # set defaults
        self.subp = None
        self.duration = '01:00'
        builder.get_object('btn-noise-brown').emit('clicked')
        builder.get_object('adj-band-center').set_value(500) # 1786
        builder.get_object('adj-band-width').set_value(500)  # 499
        builder.get_object('adj-tremolo-speed').set_value(0.033333)
        builder.get_object('adj-tremolo-depth').set_value(43)
        builder.get_object('adj-reverb').set_value(19)
        builder.get_object('adj-volume').set_value(80)
        auto_play = False

        # parse args
        for arg in args[1:]:
            try:
                a = arg.lstrip('-').split('=')
                if a[0] == 'play':
                    auto_play = True
                elif a[0] == 'noise':
                    builder.get_object(f'btn-noise-{a[1].lower()}').emit('clicked')
                else:
                    builder.get_object(f'adj-{a[0].lower()}').set_value(float(a[1]))
            except Exception as e:
                print('ARG ERROR:', arg, '::', e)
        if auto_play:
            self.playButtonClicked()

    def onDestroy(self, *args):
        if self.subp:
            self.subp.kill()
        Gtk.main_quit()

    def setNoise(self, button):
        if (button.get_active()):
            self.noise = button.get_label().lower()
        if self.subp:
            self.playButtonClicked()

    def setBandCenter(self, adj):
        self.band_center = adj.get_value()

    def setBandWidth(self, adj):
        self.band_width = adj.get_value()

    def setTremoloSpeed(self, adj):
        self.trem_speed = adj.get_value()

    def setTremoloDepth(self, adj):
        self.trem_depth = adj.get_value()

    def setReverb(self, adj):
        self.reverb = adj.get_value ()

    def setVolume(self, adj):
        self.volume = adj.get_value()/100

    def playButtonClicked(self, button=None):
        if self.subp:
            self.subp.kill()
        args = ['play', '-c2', '--null', '-talsa', 'synth', self.duration,
            f'{self.noise}noise',
            'band', '-n', str(self.band_center), str(self.band_width),
            'tremolo', str(self.trem_speed), str(self.trem_depth),
            'reverb', str(self.reverb),
            'vol', str(self.volume),
            # 'bass', '-11', 'treble' '-1',
            'fade', 'q', '.01', self.duration, '.01',
            'repeat', '99999']
        print('\n', args)
        self.subp = Popen(args)


if __name__ == "__main__":
    win = SoxNoise(sys.argv)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, win.onDestroy)
    Gtk.main()
