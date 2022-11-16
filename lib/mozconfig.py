# todo:
#  - make get_configs_from_args return an object

import argparse
import multiprocessing
import os
import platform
import sys

def platform_is_64bit():
    return sys.maxsize > 2 ** 32

def add_common_config_arguments(parser, isBrowserConfig):
    opt_group = parser.add_mutually_exclusive_group()
    opt_group.add_argument('-o', '--opt', action='store_true', help = 'Optimized build')
    opt_group.add_argument('-d', '--optdebug', action='store_true',
                           help = 'Optimized build with assertions enabled')
    if isBrowserConfig:
        opt_group.add_argument('-p', '--pgo', action='store_true',
                               help='Profile guided optimization build')

    if platform_is_64bit():
        parser.add_argument('--32bit', action='store_true', dest='target32',
                            help='Cross compile 32bit build on 64bit host')

    san_group = parser.add_mutually_exclusive_group()
    san_group.add_argument('--tsan', action='store_true', help='Thread sanitizer build')
    san_group.add_argument('--asan', action='store_true', help='Address sanitizer build')
    san_group.add_argument('--valgrind', action='store_true', help='Valgrind build')

    parser.add_argument('--small-chunk', action='store_true',
                        help='Use 256KM chunks instead of the usual 1MB')

    parser.add_argument('--concurrent', action='store_true',
                        help='GC support for concurrent marking')

def add_browser_config_arguments(parser):
    add_common_config_arguments(parser, True)
    parser.add_argument('--minimal', action='store_true',
                        help='Disable optional functionality to reduce build time')

    parser.add_argument('--android', action='store_true',
                        help='Build Android browser')

def add_shell_config_arguments(parser):
    add_common_config_arguments(parser, False)
    parser.add_argument('--armsim', action='store_true', help='ARM simulator build')
    parser.add_argument('--gcc', action='store_true', help='Build with GCC rather than clang')

def get_configs_from_args(args):
    names = []
    options = []

    def config(name):
        # Not all names may be present
        return getattr(args, name, False)

    # Don't use sccache on machines with lots of cores because it's slower.
    if multiprocessing.cpu_count() < 32:
        options.append("--with-ccache=$HOME/.mozbuild/sccache/sccache")

    if config('minimal'):
        names.append('minimal')
        options.append('--disable-av1')
        options.append('--disable-ffmpeg')
        options.append('--disable-printing')
        options.append('--disable-synth-speechd')
        options.append('--disable-webspeech')
        options.append('--disable-webrtc')

    if config('small_chunk'):
        names.append('smallChunk')
        options.append('--enable-small-chunk-size')

    if config('concurrent'):
        names.append('concurrent')
        options.append('--enable-gc-concurrent-marking')

    if config('target32'):
        names.append('32bit')
        options.append('--target=i686-pc-linux')

    if config('android'):
        names.append('android')
        options.append('--enable-application=mobile/android')
        # Defaults to armv7, or add --target=aarch64

    if config('gcc'):
        names.append('gcc')
        options.append('export CC=gcc')
        options.append('export CXX=g++')
    else:
        options.append('--enable-clang-plugin')

    if config('opt'):
        names.append('opt')
        options.append('--disable-debug')
        options.append('--enable-release')
        options.append('--enable-strip')
    elif config('pgo'):
        names.append('pgo')
        options.append('--disable-debug')
        options.append('--enable-release')
        options.append('--enable-strip')
        options.append('ac_add_options MOZ_PGO=1')
    elif config('optdebug'):
        names.append('optdebug')
        options.append('--enable-debug')
        options.append('--enable-optimize')
        options.append('--enable-gczeal')
        options.append('--enable-debug-symbols')
    else:
        options.append('--disable-optimize')
        options.append('--enable-debug')
        options.append('--enable-gczeal')
        options.append('--enable-debug-symbols')

    if config('tsan'):
        names.append('tsan')
        options.append('--enable-thread-sanitizer')
        options.append('export RUSTFLAGS="-Zsanitizer=thread"')
        options.append('unset RUSTFMT')
        add_sanitizer_options(args, options)
    elif config('asan'):
        names.append('asan')
        options.append('--enable-address-sanitizer')
        add_sanitizer_options(args, options)
    elif config('valgrind'):
        names.append('valgrind')
        options.append('--enable-valgrind')
        options.append('--disable-jemalloc')
        if '--enable-optimize' in options:
            options.remove('--enable-optimize')
            options.append('--enable-optimize="-Og -g"')

    if config('armsim'):
        platform = 'arm'
        if platform_is_64bit() and not config('target32'):
            platform = 'arm64'
        names.append(platform + 'sim')
        options.append('--enable-simulator=' + platform)

    if config('shell'):
        names.append('shell')
        options.append('--enable-application=js')
        if not config('tsan') and not config('asan'):
            options.append('--enable-warnings-as-errors')
    else:
        options.append('--disable-sandbox') # Allow content processes to access filesystem
        options.append('--without-wasm-sandboxed-libraries')
        options.append('--enable-js-shell') # Required for mach jstestbrowser

    options.append('--enable-linker=mold')

    return names, options

def add_sanitizer_options(args, options):
    # From https://firefox-source-docs.mozilla.org/tools/sanitizer/tsan.html
    # See also build/unix/mozconfig.tsan, mozconfig.asan
    options.append('--disable-jemalloc')
    options.append('--disable-profiling')
    options.append('--enable-debug-symbols')
    options.append('--disable-install-strip')
    if '--enable-optimize' in options:
        options.remove('--enable-optimize')
        options.append('--enable-optimize="-O2 -gline-tables-only"')
    if not getattr(args, 'shell', False):
        options.append('--disable-elf-hack')
        options.append('--disable-crashreporter')
        options.append('--disable-sandbox')
    options.append('export MOZ_DEBUG_SYMBOLS=1')

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
            if option.startswith('--'):
                w(f"ac_add_options {option}")
            else:
                w(option)

def setup_environment(args):
    if platform.system() == 'Linux' and args.target32:
        os.environ['PKG_CONFIG_PATH']='/usr/lib/x86_64-linux-gnu/pkgconfig'
