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
from gi.repository import Gtk, GLib, Gdk, Gio, GdkPixbuf
from subprocess import Popen


class SoxNoise:
    def __init__(self, args=[], app=None):
        self.builder = Gtk.Builder()
        self.builder.add_from_file(os.path.join(os.path.dirname(__file__), "main.ui"))
        self.builder.connect_signals(self)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self.onDestroy)

        self.window = self.builder.get_object('main-window')
        self.main_box = self.builder.get_object('main-box')
        self.play_button = self.builder.get_object('play-button')
        self.spec_button = self.builder.get_object('spec-button')
        self.spec_image = self.builder.get_object('spec-image')
        self.band_center = self.builder.get_object('adj-band-center')
        self.band_width = self.builder.get_object('adj-band-width')
        self.tremolo_speed = self.builder.get_object('adj-tremolo-speed')
        self.tremolo_depth = self.builder.get_object('adj-tremolo-depth')
        self.effects = self.builder.get_object('effects-expander')
        self.reverb = self.builder.get_object('adj-reverb')
        self.volume = self.builder.get_object('adj-volume')
        self.menu = self.builder.get_object('popover-menu')
        if app:  self.window.set_application(app)
        default_conf = os.getenv('XDG_CONFIG_HOME', '~/.config') + '/sox-noise-default.sxn'
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
        parser.add_argument('--save',          help='Save sound to filename')
        parser.add_argument('--output',        choices=output_mapping.keys(), default='default', help='Output device/format')
        parser.add_argument('--spectrogram',   action='store_true',    help='Show the spectrogram')
        parser.add_argument('--extras',        nargs='+',              help='Extra arguments to pass to sox')
        parser.add_argument('--version',       action='version',       help=version, version=version)
        self.defaults = parser.parse_args([])
        self.parser = parser

        # parse config
        self.cpath = os.path.expanduser(cargs.config or default_conf)
        if os.path.exists(self.cpath):
            copts = self.parseConfig(self.cpath)
            parser.set_defaults(**copts)  # unfortunatly this borks the ArgumentDefaultsHelpFormatter
            self.pargs = parser.parse_args(remaining_args)
            print("Config:", self.cpath, copts, file=sys.stderr)  # avoid printing on help
        else:
            self.pargs = parser.parse_args(remaining_args)
            if cargs.config:  print('Config file not found:', self.cpath, file=sys.stderr)

        # set initial values
        self.subp = None
        self.save = self.pargs.save
        self.noise = self.pargs.noise
        self.duration = self.pargs.duration
        self.last_sound_fname = 'noise.ogg'
        self.last_config_fname = 'noise.sxn'
        self.resetSettings(self.pargs)
        out_split = self.pargs.output.split(',', 1)
        self.output = output_mapping.get(out_split[0])
        if len(out_split) > 1:
            # allows for "--output=alsa,hw:0,1"
            self.output = [self.output[0], out_split[1]]
        if self.pargs.output not in ['wav', 'sox'] and os.fstat(0) != os.fstat(1):
            print('WARNING: Redirect Detected: Use the "--output=wav" or "--output=sox" arguments to redirect sound data!', file=sys.stderr)
        if self.pargs.effects:
            self.effects.set_expanded(True)
        if not self.pargs.hide:
            self.window.show_all()
        self.window.set_focus(self.play_button)
        self.spec_button.set_active(self.pargs.spectrogram)
        if self.pargs.hide or self.pargs.play:
            self.play_button.set_active(True)
        if self.pargs.tray:
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

    def parseConfig(self, cpath):
        config = configparser.ConfigParser()
        config.read([cpath])
        copts = { k.replace('-', '_'): v
                  for k, v in config.items(config.sections()[0]) }
        if 'extras' in copts:  copts['extras'] = copts['extras'].split(' ')
        return copts

    def resetSettings(self, pargs=None):
        if not pargs or not isinstance(pargs, argparse.Namespace):
            pargs = self.defaults  # use defaults when called by a widget
        self.band_center.set_value(pargs.band_center)
        self.band_width.set_value(pargs.band_width)
        self.tremolo_speed.set_value(pargs.tremolo_speed)
        self.tremolo_depth.set_value(pargs.tremolo_depth)
        self.reverb.set_value(pargs.reverb)
        self.volume.set_value(pargs.volume)
        self.needs_update = self.noise == pargs.noise
        self.extras = pargs.extras
        self.noise = pargs.noise
        self.fade = pargs.fade
        self.builder.get_object(f'btn-noise-{pargs.noise}').emit('clicked')
        self.doneAdjusting()

    def onDestroy(self, *args):
        if self.subp:  self.subp.kill()

    def onKeyPress(self, widget, event):
        # TODO: configurable keybinds
        # play/pause on space
        if event.keyval == Gdk.KEY_space:
            self.play_button.set_active(not self.play_button.get_active())
            return True  # prevent default behaviour
        elif event.state & Gdk.ModifierType.CONTROL_MASK:
            # close on Ctrl+Q, etc.
            if event.keyval in [Gdk.KEY_q, Gdk.KEY_w, Gdk.KEY_c, Gdk.KEY_Q, Gdk.KEY_W, Gdk.KEY_C]:
                self.window.destroy()
            # effects on Ctrl+E
            elif event.keyval in [Gdk.KEY_e, Gdk.KEY_E]:
                self.effects.set_expanded(not self.effects.get_expanded())
            # spectrogram on Ctrl+D
            elif event.keyval in [Gdk.KEY_d, Gdk.KEY_D]:
                self.spec_button.set_active(not self.spec_button.get_active())
            # load on Ctrl+O
            elif event.keyval in [Gdk.KEY_o, Gdk.KEY_O]:
                self.loadSettings()
            # save on Ctrl+S
            elif event.keyval in [Gdk.KEY_s, Gdk.KEY_S]:
                if event.state & Gdk.ModifierType.SHIFT_MASK:
                    self.saveSound(True)
                else:
                    self.saveSettings()

    def valueChanged(self, adj):
        # slider changed
        self.needs_update = True

    def setNoise(self, button):
        if (button.get_active()):
            self.noise = button.get_label().lower()
            self.play()  # resume playback
            self.saveSound()
            self.showSpectrogram()

    def doneAdjusting(self, widget=None, event=None):
        # resume playback with new settings
        if self.needs_update:
            self.saveSound()
            self.needs_update = False
            if not widget or widget.get_name().startswith('band_'):
                self.showSpectrogram()
            if self.subp:  self.play()

    def closeMenu(self, widget=None):
        self.menu.popdown()

    def saveSettings(self, widget=None):
        filename = self.dialog('Save Settings', conf=True, save=True, filename=self.last_config_fname)
        if not filename:  return
        self.last_config_fname = filename
        config = configparser.ConfigParser()
        args = {
            'play': self.play_button.get_active(),
            'noise': self.noise,
            **{ k: int(getattr(self, k).get_value())
                for k in ['volume', 'band_center', 'band_width',
                          'reverb', 'tremolo_speed', 'tremolo_depth'] },
            'effects': self.pargs.effects,
            'spectrogram': self.spec_button.get_active(),
            'output': self.pargs.output,
            'duration': self.duration,
            'fade': self.fade,
            'tray': self.pargs.tray,
            'hide': self.pargs.hide,
            'extras': ' '.join(self.extras or []),
        }
        config.read_dict({'sox-noise': {
            k:v for k,v in args.items() if v and v != getattr(self.defaults, k) }})
        with open(filename, 'w') as configfile:
            config.write(configfile)

    def loadSettings(self, widget=None):
        filename = self.dialog('Load Settings', conf=True, filename=self.last_config_fname)
        if not filename:  return
        self.last_config_fname = filename
        copts = self.parseConfig(filename)
        self.parser.set_defaults(**vars(self.defaults))
        self.parser.set_defaults(**copts)
        pargs = self.parser.parse_args([])
        self.resetSettings(pargs)

    def saveSound(self, widget=None):
        if widget:  # button clicked
            filename = self.dialog('Save Sound', audio=True, save=True, filename=self.last_sound_fname)
            if not filename:  return
        elif self.save:
            filename = self.save
        else:  return
        self.last_sound_fname = filename
        args = self.getArgs([filename], repeat=False)
        # print('\n save===>', ' '.join(args), file=sys.stderr)
        Popen(args)

    def dialog(self, title, audio=False, conf=False, save=False, filename=None):
        # show FileChooserDialog and return filename
        dialog = Gtk.FileChooserDialog(title=title, parent=self.window, action=Gtk.FileChooserAction.SAVE if save else Gtk.FileChooserAction.OPEN)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE if save else Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        if filename:
            if filename == os.path.basename(filename):  # if filename not full path
                dialog.set_current_name(filename)
            else:
                dialog.set_filename(filename)
        if audio:
            fltr = Gtk.FileFilter()
            fltr.set_name('Audio files')
            fltr.add_mime_type('audio/*')
            dialog.add_filter(fltr)
        if conf:
            fltr = Gtk.FileFilter()
            fltr.set_name('Config files')
            fltr.add_pattern('*.sxn')
            dialog.add_filter(fltr)
        fltr = Gtk.FileFilter()
        fltr.set_name('All files')
        fltr.add_pattern('*')
        dialog.add_filter(fltr)
        selected = None
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            selected = dialog.get_filename()
        dialog.destroy()
        return selected

    def showSpectrogram(self, widget=None, event=None):
        if not self.spec_button.get_active():
            return self.spec_image.hide()

        # TODO: wait for effects expander to be done resizing and update
        # GLib.idle_add(self.genSpec, self)

        # NOTE: -y values should be "one more than a multiple of two" for optimal performance. Use -Y to truncate
        # MAGIC: height - 9 happens to remove padding, etc for me (87 w/o -r)
        height = self.main_box.get_allocation().height - 9
        args = self.getArgs(['--null'], full=False) + [
            'spectrogram', '-o-', '-x200', f'-y{height}','-r']
        # print('\n spec===>', ' '.join(args), file=sys.stderr)
        spec = GLib.spawn_async(args, flags=GLib.SpawnFlags.SEARCH_PATH, standard_output=True)
        GLib.io_add_watch(spec[2], GLib.IO_IN, self.specDone)

    def specDone(self, fd, x):
        with os.fdopen(fd, "rb") as spec:
            loader = GdkPixbuf.PixbufLoader()
            loader.write(spec.read())
            loader.close()
            self.spec_image.set_from_pixbuf(loader.get_pixbuf())
            self.spec_image.show()

    def getArgs(self, output, full=True, repeat=True):
        vol = self.volume.get_value()
        return ['sox', f'-c{2 if full else 1}', '--null', *output,
            'synth', f'0:{self.duration if full else 1}', f'{self.noise}noise',
            'band', '-n', str(self.band_center.get_value()), str(self.band_width.get_value())] + ([
            'tremolo', str(self.tremolo_speed.get_value()/self.duration), str(self.tremolo_depth.get_value()),
            'reverb', str(self.reverb.get_value())] + ([
            'vol', str(vol/100)] if vol <= 100 else ['gain', str(vol-100)]) + [
            'fade', 'q', str(self.fade), f'0:{self.duration}', str(self.fade)] if full else []) + (
            self.extras if self.extras else []) + ([
            'repeat', '-'] if full and repeat else [])

    def play(self, button=None):
        if self.subp:  self.subp.kill()
        if self.play_button.get_active():
            args = self.getArgs(self.output)
            print('\n ===>', ' '.join(args), file=sys.stderr)
            self.subp = Popen(args)


# Integrates App with DE rich-features
class SoxNoiseApp(Gtk.Application):
    def __init__(self, win=None):
        super().__init__(application_id='thann.sox-noise', flags=(
            Gio.ApplicationFlags.NON_UNIQUE |
            Gio.ApplicationFlags.HANDLES_OPEN
        ))

    def run(self, args):
        # circumvent options parsing
        self.args = args[1:]
        super().run()

    def do_activate(self, args=[]):
        self.register()
        self.app = SoxNoise(self.args, app=self)

    # TODO:
    # def do_open(files, hint):
    #     self.app.loadSettings(files)


version = 'Unknown'
vfilename = os.path.join(os.path.dirname(__file__), '.version')
if os.path.exists(vfilename):
    # NOTE: version file is created externally by setup.py
    with open(vfilename, 'r') as ver:
        version = ver.read() or version

def start():
    sys.exit(SoxNoiseApp().run(sys.argv))

if __name__ == '__main__':
    start()
