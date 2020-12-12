# todo:
#  - armsim
#  - tsan

import argparse
import os
import platform

def add_common_config_arguments(parser):
    opt_group = parser.add_mutually_exclusive_group()
    opt_group.add_argument('-o', '--opt', action='store_true', help = 'Optimized build')
    opt_group.add_argument('-d', '--optdebug', action='store_true',
                           help = 'Optimized build with assertions enabled')

    parser.add_argument('--32bit', action='store_true', dest='target32',
                        help='Cross compile 32bit build on 64bit host')

def add_browser_config_arguments(parser):
    parser.add_argument('--minimal', action='store_true',
                        help='Disable optional functionality to reduce build time')

def get_configs_from_args(args):
    names = []
    options = []

    options.append("--with-ccache=$HOME/.mozbuild/sccache/sccache")
    options.append("--enable-warnings-as-errors")

    if args.opt:
        names.append('opt')
        options.append('--enable-optimize')
        options.append('--disable-debug')
    elif args.optdebug:
        names.append('optdebug')
        options.append('--enable-optimize')
        options.append('--enable-debug')
        options.append('--enable-gczeal')
    else:
        options.append('--disable-optimize')
        options.append('--enable-debug')
        options.append('--enable-gczeal')

    if args.target32:
        names.append('32bit')
        options.append('--target=i686-pc-linux')

    if getattr(args, 'shell', False):
        names.append('shell')
        options.append('--enable-application=js')

    if getattr(args, 'minimal', False):
        names.append('minimal')
        options.append('--disable-av1')
        options.append('--disable-cranelift')
        options.append('--disable-ffmpeg')
        options.append('--disable-js-shell')
        options.append('--disable-printing')
        options.append('--disable-synth-speechd')
        options.append('--disable-webspeech')
        options.append('--disable-webrtc')

    return names, options

def get_build_name(config_names):
    """
    Get a canonical build name from a list of configs.
    """
    name_elements = config_names.copy()
    if not name_elements:
        name_elements.append("default")
    return '-'.join(name_elements)

def write_mozconfig(build_dir, options, build_config):
    with open(build_config, "w") as file:
        def w(line):
            file.write(f"{line}\n")

        w(f"mk_add_options MOZ_OBJDIR=@TOPSRCDIR@/{build_dir}")
        w("mk_add_options AUTOCLOBBER=1")
        for option in options:
            w(f"ac_add_options {option}")

def setup_environment(args):
    if platform.system() == 'Linux' and args.target32:
        os.environ['PKG_CONFIG_PATH']='/usr/lib/x86_64-linux-gnu/pkgconfig'
