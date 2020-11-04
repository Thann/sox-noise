#!/usr/bin/env python
import os
from setuptools import setup, find_packages

description = "Noise generator GUI powered by Sound eXchange"

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

def get_version():
    from subprocess import Popen, PIPE
    try:
        from subprocess import DEVNULL # py3
    except ImportError:
        import os
        DEVNULL = open(os.devnull, 'wb')

    def run(*cmd):
        return (Popen(cmd, stderr=DEVNULL, stdout=PIPE)
                .communicate()[0].decode('utf8').strip())

    return(run('git', 'describe', '--tags').replace('-','.post',1).replace('-','+',1)
        or '0.0.0.post{}+g{}'.format(
            run('git', 'rev-list', '--count', 'HEAD'),
            run('git', 'rev-parse', '--short', 'HEAD')))

setup(
    name = "sox-noise",
    version = get_version(),
    author = "Jonathan Knapp",
    author_email = "jaknapp8@gmail.com",
    description = description,
    license = "UNLICENSE",
    keywords = "sox noise generator",
    url = "http://github.com/thann/sox-noise",
    long_description=read('README.md'),
    classifiers=[
        "Development Status :: 4 - Beta",
        # "Development Status :: 5 - Production/Stable",
        "Topic :: Multimedia :: Sound/Audio :: Sound Synthesis",
        "License :: OSI Approved :: The Unlicense (Unlicense)",
    ],
    packages=[''],
    package_data={'': ['main.ui']},
    include_package_data=True,
    py_modules=["sox_noise"],
    install_requires=['wheel', 'PyGObject'],  # pycairo ?
    entry_points={
        'gui_scripts': [
            'sox-noise=sox_noise:start',
        ],
    },
    setup_requires=['wheel', 'install_freedesktop>=0.2.0'],
    dependency_links=[
        "https://github.com/thann/install_freedesktop/tarball/master#egg=install_freedesktop-0.2.0"
    ],
    desktop_entries={
        'sox-noise': {
            'filename': 'thann.sox-noise',
            'Name': 'SoX Noise',
            'Categories': 'AudioVideo;Audio;Player',
            'Comment': description,
            'Icon': 'audio-volume-high',
        },
    },
)
