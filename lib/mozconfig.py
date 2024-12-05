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
    opt_group.add_argument('--release', action='store_true', help = 'Release build')
    opt_group.add_argument('-o', '--opt', action='store_true', help = 'Optimized build')
    opt_group.add_argument('-d', '--optdebug', action='store_true',
                           help = 'Optimized build with assertions enabled')

    if platform_is_64bit():
        parser.add_argument('--32bit', action='store_true', dest='target32',
                            help='Cross compile 32bit build on 64bit host')

    san_group = parser.add_mutually_exclusive_group()
    san_group.add_argument('--tsan', action='store_true', help='Thread sanitizer build')
    san_group.add_argument('--asan', action='store_true', help='Address sanitizer build')
    san_group.add_argument('--valgrind', action='store_true', help='Valgrind build')

    sync_group = parser.add_mutually_exclusive_group()
    sync_group.add_argument('-S', '--no-sync', action='store_true',
                            help = 'Don\'t sync cloned branch')
    sync_group.add_argument('-s', '--sync-dir',
                            help = 'Sync specified directory before build')
    sync_group.add_argument('-m', '--sync-js-only', dest='sync_dir', action='store_const', const="js",
                            help = 'Sync js source only before build')

    parser.add_argument('--concurrent', action='store_true',
                        help='GC support for concurrent marking')

    parser.add_argument('--ctypes', action='store_true',
                        help='GC support for concurrent marking')

    parser.add_argument('-U', '--no-unify', action='store_false', dest='unified', default=True,
                        help='Disable unified build')

def add_browser_config_arguments(parser):
    add_common_config_arguments(parser, True)
    parser.add_argument('--minimal', action='store_true',
                        help='Disable optional functionality to reduce build time')

    parser.add_argument('--android', action='store_true',
                        help='Build Android browser')

    parser.add_argument('--ccov', action='store_true', help='Coverage build')

def add_shell_config_arguments(parser):
    add_common_config_arguments(parser, False)
    parser.add_argument('--armsim', action='store_true', help='ARM simulator build')
    parser.add_argument('--gcc', action='store_true', help='Build with GCC rather than clang')
    parser.add_argument('--pbl', action='store_true', help='Portable baseline interpreter')

def get_configs_from_args(args):
    names = []
    options = []

    def config(name):
        # Not all names may be present
        return getattr(args, name, False)

    # Don't use sccache on machines with lots of cores because it's slower.
    if multiprocessing.cpu_count() < 32:
        options.append("--with-ccache=sccache")

    if config('minimal'):
        names.append('minimal')
        options.append('--disable-av1')
        options.append('--disable-ffmpeg')
        options.append('--disable-printing')
        options.append('--disable-synth-speechd')
        options.append('--disable-webspeech')
        options.append('--disable-webrtc')

    if config('ctypes'):
        # Required for hazard analysis but doesn't build everywhere.
        names.append('ctypes')
        options.append('--enable-ctypes')

    if config('concurrent'):
        names.append('concurrent')
        options.append('--enable-gc-concurrent-marking')

    if config('pbl'):
        names.append('pbl')
        options.append('--enable-portable-baseline-interp')
        options.append('--enable-portable-baseline-interp-force')

    if config('target32'):
        names.append('32bit')
        options.append('--target=i686-pc-linux')

    if config('android'):
        names.append('android')
        options.append('--enable-application=mobile/android')
        options.append('--target=aarch64') # Defaults to armv7
        # todo: above conflicts with --target32 option

    if config('gcc'):
        names.append('gcc')
        options.append('export CC=gcc')
        options.append('export CXX=g++')
    else:
        if platform.system() == 'Linux' and not config('target32'):
            # Currently broken on MacOS?
            options.append('--enable-clang-plugin')

    if config('release'):
        names.append('release')
        options.append('MOZILLA_OFFICIAL=1')
        options.append('--disable-debug')
        options.append('--enable-release')
        options.append('--as-milestone=release')
        options.append('--enable-official-branding')
        options.append('--enable-rust-simd')
        options.append('--enable-strip')
        options.append('--disable-tests')
        if platform.system() == 'Linux':
            # Causes link failure on MacOS
            options.append('MOZ_LTO=cross')
    elif config('opt'):
        names.append('opt')
        options.append('--disable-debug')
        options.append('--enable-optimize')
        options.append('--as-milestone=release')  # Reduces poisoning.
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
        options.remove('--enable-clang-plugin')
        options.append('--enable-valgrind')
        options.append('--disable-jemalloc')
        options.append('--disable-install-strip')
        options.append('--disable-gtest-in-build')
        if '--enable-optimize' in options:
            options.remove('--enable-optimize')
            options.append('--enable-optimize="-Og -g"')
        if not config('shell'):
            options.append('--disable-dmd')
            options.append('--enable-logrefcnt')

    if config('armsim'):
        if platform_is_64bit() and not config('target32'):
            arm_platform = 'arm64'
        else:
            arm_platform = 'arm'
        names.append(arm_platform + 'sim')
        options.append('--enable-simulator=' + arm_platform)

    if config('ccov'):
        names.append('ccov')
        options.append('--enable-coverage')

        options.append("--enable-debug-symbols=-g1")
        options.append("--disable-sandbox")
        options.append("--disable-warnings-as-errors")
        options.append("--without-wasm-sandboxed-libraries")
        options.append("CLANG_LIB_DIR=~/.mozbuild/clang/lib/clang/16/lib/darwin")
        options.append('export LDFLAGS="-coverage -L$CLANG_LIB_DIR"')
        options.append('export LIBS="-lclang_rt.profile_osx"')
        options.append('export RUSTFLAGS="-Ccodegen-units=1 -Zprofile -Cpanic=abort -Zpanic_abort_tests -Clink-dead-code -Coverflow-checks=off"')
        options.append('export RUSTDOCFLAGS="-Cpanic=abort"')

    if config('shell'):
        names.append('shell')
        options.append('--enable-application=js')
        # Currently producing binaries that crash for the browser
        # Doesn't support LTO
        # options.append('--enable-linker=mold')
    else:
        options.append('--disable-sandbox') # Allow content processes to access filesystem
        options.append('--without-wasm-sandboxed-libraries')
        options.append('--enable-js-shell') # Required for mach jstestbrowser

    if not config('tsan') and not config('asan') and not config('gcc'):
        options.append('--enable-warnings-as-errors')

    if not config('unified'):
        names.append('nonunified')
        options.append('--disable-unified-build')

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
