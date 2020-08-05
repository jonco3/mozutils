# Configurations for SpiderMonkey builds

import os
import sys

from mozutils import *

config_names = []
config_groups = {}
config_options = {}
config_compiler_exes = {}
config_env_vars = {}
config_group_defaults = {}

def add_config(name, groups, options = [], compiler_c_exe = None, compiler_cpp_exe = None,
               env_vars = None):
    global config_names, config_groups, config_options, config_compiler_exes, config_env_vars
    assert name not in config_names
    config_names.append(name)
    config_groups[name] = groups
    if isinstance(options, list):
        config_options[name] = options
    elif options:
        config_options[name] = options.split(" ")
    else:
        config_options[name] = []
    if compiler_c_exe or compiler_cpp_exe:
        config_compiler_exes[name] = (compiler_c_exe, compiler_cpp_exe)
    if env_vars:
        config_env_vars[name] = env_vars

x86_options = '--target=i686-pc-linux'
arm_options = '--with-arch=armv7-a --with-fpu=vfp --with-thumb --without-intl-api'

add_config('debug',        'opt', ['--enable-gczeal',
                                   '--enable-debug',
                                   '--disable-optimize',
                                   '--enable-oom-breakpoint'])
add_config('optdebug',     'opt', ['--enable-gczeal',
                                   '--enable-debug',
                                   '--enable-optimize'])
add_config('opt',          'opt', ['--disable-debug',
                                   '--enable-optimize',
                                   '--enable-release'])
add_config('profile',      'opt',  ['--disable-debug',
                                    '--enable-optimize',
                                    '--enable-profiling'])
config_group_defaults['opt'] = 'debug'

add_config('armsim',       [], '--enable-simulator=arm')
add_config('arm64sim',     [], '--enable-simulator=arm64')
add_config('mipssim',      [], '--enable-simulator=mips32')
add_config('mips64sim',    [], '--enable-simulator=mips64')
add_config('nounified',    [], '--disable-unified-compilation')
add_config('noion',        [], '--disable-ion')
add_config('gctrace',      [], '--enable-gc-trace')
add_config('valgrind',     [], ['--enable-valgrind'])
add_config('smallchunk',   [], '--enable-small-chunk-size')
add_config('nointl',       [], '--without-intl-api')
add_config('dist',         [])

add_config('noggc',        'gc', '--disable-gcgenerational')

add_config('clang',        'compiler', [], 'clang', 'clang++')
add_config('gcc',          'compiler', [], 'gcc', 'g++')
add_config('gcc47',        'compiler', [], 'gcc-4.7', 'g++-4.7')
add_config('gcc32',        'compiler', '--target=i686-pc-linux', 'gcc -m32', 'g++ -m32',
           { 'PKG_CONFIG_LIBDIR': '/usr/lib/pkgconfig', 'AR': 'ar' })
add_config('armsf',        'compiler',
           arm_options + ' --target=arm-linux-gnueabi --with-float-abi=softfp',
           'arm-linux-gnueabi-gcc', 'arm-linux-gnueabi-g++')
add_config('armhf',        'compiler',
           arm_options + ' --target=arm-linux-gnueabihf --with-float-abi=hard',
           'arm-linux-gnueabihf-gcc', 'arm-linux-gnueabihf-g++')

# 12/02/18: Clang is 30% faster at debug builds on linux and marginally
# faster at optdebug
config_group_defaults['compiler'] = 'clang'


if sys.platform == 'darwin':
    llvm_path = '/usr/local/opt/llvm38/lib/llvm-3.8'
    tsan_env = {
        'AR': 'ar',
        'CFLAGS': '-fsanitize=thread -fPIC -pie',
        'CXXFLAGS': '-fsanitize=thread -fPIC -pie -I%s/include/c++/v1' % llvm_path,
        'LDFLAGS': '-fsanitize=thread -fPIC -pie -L%s/lib' % llvm_path }
else:
    tsan_env = {
        'AR': 'ar',
        'CFLAGS': '-fsanitize=thread -fPIC',
        'CXXFLAGS': '-fsanitize=thread -fPIC',
        'LDFLAGS': '-fsanitize=thread -fPIC' }

# TODO: decoder says: for the future, you should be able to substitute
# the llvm-hacks flag with --enable-thread-sanitizer

add_config('tsan',
           ['opt', 'compiler'],
           ['--disable-debug',
            '--enable-optimize',
            '--without-intl-api',
            '--enable-thread-sanitizer'],
           'clang', 'clang++',
           tsan_env)

add_config('asan',
           ['opt', 'compiler'],
           ['--enable-address-sanitizer',
            '--disable-jemalloc',
            '--disable-debug',
            '--enable-optimize'],
           'clang', 'clang++')

common_options = [
    '--with-ccache',
    '--enable-nspr-build',
    '--enable-ctypes',
    '--disable-cranelift',
    '--enable-warnings-as-errors'
]

if sys.platform == 'darwin':
    common_options.append('--with-macos-sdk=/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX10.11.sdk')

def get_configs_from_args(args):
    """
    Get a list of configs from the command line arguments parsed by argparse.
    """

    configs = args.configs
    if not isinstance(configs, list):
        # Why, argparse?
        configs = [configs]
    if 'default' in configs:
        configs.remove('default')
    if args.opt:
        configs.append('opt')
    if args.optdebug:
        configs.append('optdebug')
    if args.profile:
        configs.append('profile')
    if args.dist:
        configs.append('dist')

    # Check for mutally exclusive configs
    config_groups_specified = {}
    for config in configs:
        assert config in config_names, "Bad config: " + config
        groups = config_groups[config]
        if not isinstance(groups, list):
            groups = [groups]
        for group in groups:
            if group in config_groups_specified:
                sys.exit("Config %s conflicts with previous config %s" %
                         (config, config_groups_specified[group]))
            config_groups_specified[group] = config

    # Add config group defaults
    for group in config_group_defaults.keys():
        if group not in config_groups_specified:
            configs.append(config_group_defaults[group])

    # Make sure args.dist is in sync with dist config
    args.dist = 'dist' in configs

    return configs

def get_build_name(configs):
    """
    Get a canonical build name from a list of configs.
    """
    name_elements = []
    for config in config_names:
        if config in configs and config not in config_group_defaults.values():
            name_elements.append(config)
    if not name_elements:
        name_elements.append("default")
    return '-'.join(name_elements)
