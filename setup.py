#!/usr/bin/env python
import os
from setuptools import setup, find_packages

description = "Noise generator GUI powered by Sound eXchange"

def read(fname):
    with open(os.path.join(os.path.dirname(__file__), fname)) as file:
        return file.read()

def get_version():
    from subprocess import Popen, PIPE
    try:
        from subprocess import DEVNULL # py3
    except ImportError:
        DEVNULL = open(os.devnull, 'wb')

    def run(*cmd):
        return (Popen(cmd, stderr=DEVNULL, stdout=PIPE)
                .communicate()[0].decode('utf8').strip())

    return(run('git', 'describe', '--tags').replace('-','.post',1).replace('-','+',1)
        or '0.0.0.post{}+g{}'.format(
            run('git', 'rev-list', '--count', 'HEAD'),
            run('git', 'rev-parse', '--short', 'HEAD')))

# write version file
version = get_version()
filename = os.path.join(os.path.dirname(__file__), ".version")
with open(filename, 'w') as vfile:
    vfile.write(version)

setup(
    name = "sox-noise",
    version = version,
    author = "Jonathan Knapp",
    author_email = "jaknapp8@gmail.com",
    description = description,
    license = "UNLICENSE",
    keywords = "sox noise generator",
    url = "http://github.com/thann/sox-noise",
    long_description = description,
    # long_description=read('README.md'),
    classifiers=[
        "Development Status :: 4 - Beta",
        # "Development Status :: 5 - Production/Stable",
        "Topic :: Multimedia :: Sound/Audio :: Sound Synthesis",
        "License :: OSI Approved :: The Unlicense (Unlicense)",
    ],
    # NOTE: This causes a warning but is seemingly necessary unless everything is in a sub-folder =/
    packages=[''],
    package_data={'': ['main.ui', '.version']},
    include_package_data=True,
    py_modules=["sox_noise"],
    install_requires=['wheel', 'PyGObject'],
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
