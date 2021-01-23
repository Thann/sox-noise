#!/usr/bin/env python
# Noise generator GUI powered by SoX
# fair-used off of: https://gist.github.com/rsvp/1209835

import os
import gi
import sys
import signal
import argparse
import configparser
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk
from subprocess import Popen


class SoxNoise:
    def __init__(self, args=[]):
        builder = Gtk.Builder()
        builder.add_from_file(os.path.join(os.path.dirname(__file__), "main.ui"))
        builder.connect_signals(self)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self.onDestroy)

        self.subp = None
        self.window = builder.get_object("main-window")
        self.play_button = builder.get_object('play-button')
        self.band_center = builder.get_object('adj-band-center')
        self.band_width = builder.get_object('adj-band-width')
        self.trem_speed = builder.get_object('adj-tremolo-speed')
        self.trem_depth = builder.get_object('adj-tremolo-depth')
        self.reverb = builder.get_object('adj-reverb')
        self.volume = builder.get_object('adj-volume')
        default_conf = '~/.config/sox-noise.conf'
        output_mapping = {
            'pulse':   ['-tpulseaudio'],
            'alsa':    ['-talsa'],
            'wav':     ['-twav', '-'],
            'sox':     ['-tsox', '-'],
            'default': ['-d'],
        }

        # parse args
        conf_parser = argparse.ArgumentParser(add_help=False)
        conf_parser.add_argument('--config', help=f'Configuration file location (default: {default_conf})')
        cargs, remaining_args = conf_parser.parse_known_args(args)
        parser = argparse.ArgumentParser(description='Noise Generator powered by SoX.', parents=[conf_parser])
        parser.add_argument('noise', choices=['brown', 'pink', 'white', 'tpdf'],
            nargs='?', default='brown', help='The "color" of noise')
        parser.add_argument('--play',          action='store_true',    help='Start playing on open')
        parser.add_argument('--volume',        type=int,  default=80,  help='[1-120]')
        parser.add_argument('--band-center',   type=int,  default=500, help='Band-pass filter around center frequency [1-2000] (Hz) ')
        parser.add_argument('--band-width',    type=int,  default=500, help='Band-pass filter width [1-1000]')
        parser.add_argument('--effects',       action='store_true',    help='Show effects options')
        parser.add_argument('--reverb',        type=int,  default=20,  help='Small amounts make it sound more natural [0-100]')
        parser.add_argument('--tremolo-speed', type=int,  default=2,   help='Periodically raise and lower the volume [0-10] (cycles per duration)')
        parser.add_argument('--tremolo-depth', type=int,  default=30,  help='Tremolo intensity [0-100]')
        parser.add_argument('--duration',      type=int,  default=60,  help='How many seconds to generate noise before looping (default: 60)')
        parser.add_argument('--fade',          type=float,default=.005,help='How long to fade in/out on loop. Prevents clicking/popping (default: 0.005)')
        parser.add_argument('--tray',          action='store_true',    help='Show an icon in the system tray')
        parser.add_argument('--hide',          action='store_true',    help="Don't show the window")
        parser.add_argument('--output',        default='default',      help='Output device/format: {'+ ','.join(output_mapping.keys()) +'}, or filename')

        # parse config
        cpath = os.path.expanduser(cargs.config or default_conf)
        if os.path.exists(cpath):
            config = configparser.ConfigParser()
            config.read([cpath])
            copts = { k.replace('-','_'):v for k,v in config.items(config.sections()[0]) }
            parser.set_defaults(**copts)  # unfortunatly this borks the ArgumentDefaultsHelpFormatter
            pargs = parser.parse_args(remaining_args)
            print("Config:", cpath, copts, file=sys.stderr)  # avoid printing on help
        else:
            pargs = parser.parse_args(remaining_args)
            if cargs.config:  print("No config file found:", cpath, file=sys.stderr)

        # set initial values
        self.play_immedietly = False
        self.band_center.set_value(pargs.band_center)
        self.band_width.set_value(pargs.band_width)
        self.trem_speed.set_value(pargs.tremolo_speed)
        self.trem_depth.set_value(pargs.tremolo_depth)
        self.reverb.set_value(pargs.reverb)
        self.volume.set_value(pargs.volume)
        self.duration = pargs.duration
        self.noise = pargs.noise
        self.fade = pargs.fade
        self.needs_update = False
        self.repeat = True
        builder.get_object(f'btn-noise-{pargs.noise}').emit('clicked')

        out_split = pargs.output.split(',', 1)
        self.output = output_mapping.get(out_split[0])
        if not self.output:  # output to file
            self.repeat = False
            self.output = [os.path.expanduser(pargs.output)]
        elif len(out_split) > 1:
            # allows for "--output=alsa,hw:0,1"
            self.output = [self.output[0], out_split[1]]
        if pargs.output not in ['wav', 'sox'] and os.fstat(0) != os.fstat(1):
            print('WARNING: Redirect Detected: Use the "--output=wav" or "--output=sox" arguments to redirect sound data!', file=sys.stderr)

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
                print('TRAY ERROR:', e, file=sys.stderr)

        # apply styles
        # Hack: to align the tremolo-speed scale
        css = b'.lpad { margin-left: 1.1ex; }'
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(css)
        Gtk.StyleContext().add_provider_for_screen(Gdk.Screen.get_default(),
            css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def onDestroy(self, *args):
        if self.subp:
            self.subp.kill()
        Gtk.main_quit()

    def onKeyPress(self, widget, event):
        # Close on Ctrl+Q, etc.
        if (event.keyval in [Gdk.KEY_q, Gdk.KEY_w, Gdk.KEY_c] and
            event.state & Gdk.ModifierType.CONTROL_MASK):
            self.onDestroy()

    def setNoise(self, button):
        if (button.get_active()):
            self.noise = button.get_label().lower()
            self.play()  # resume playback

    def valueChanged(self, adj):
        # slider changed
        if self.play_immedietly:
            self.play_immedietly = False
            self.play()
        else:
            self.needs_update = True

    def doneAdjusting(self, widget=None, event=None):
        # Hack: "scroll events" trigger doneAdjusting before valueChanged
        scroll = isinstance(event, Gtk.ScrollType)
        # resume playback with new settings
        if self.subp:
            if scroll:
                self.play_immedietly = True
            if self.needs_update:
                self.needs_update = False
                self.play()

    def play(self, button=None):
        if self.subp:
            self.subp.kill()

        if self.play_button.get_active():
            vol = self.volume.get_value()
            args = ['sox', '-c2', '--null'] + self.output + [
                'synth', f'0:{self.duration}', f'{self.noise}noise',
                'band', '-n', str(self.band_center.get_value()), str(self.band_width.get_value()),
                'tremolo', str(self.trem_speed.get_value()/self.duration), str(self.trem_depth.get_value()),
                'reverb', str(self.reverb.get_value())] + ([
                'vol', str(vol/100)] if vol <= 100 else ['gain', str(vol-100)]) + [
                # 'bass', '-11', 'treble' '-1',
                'fade', 'q', str(self.fade), f'0:{self.duration}', str(self.fade)] + ([
                'repeat', '-'] if self.repeat else [])
            print('\n ===>', ' '.join(args), file=sys.stderr)
            self.subp = Popen(args)


def start():
    SoxNoise(sys.argv[1:])
    Gtk.main()

if __name__ == "__main__":
    start()
