# Configurations for SpiderMonkey builds

config_names = []
config_group = {}
config_options = {}
config_compiler_exes = {}
config_env_vars = {}
config_group_defaults = {}

def add_config(name, group, options, compiler_c_exe = None, compiler_cpp_exe = None, env_vars = None):
    global config_names, config_group, config_options, config_compiler_exes, config_env_vars
    assert name not in config_names
    config_names.append(name)
    config_group[name] = group
    config_options[name] = options if options else ''
    if compiler_c_exe or compiler_cpp_exe:
        config_compiler_exes[name] = (compiler_c_exe, compiler_cpp_exe)
    if env_vars:
        config_env_vars[name] = env_vars

x86_options = '--target=i686-pc-linux'
arm_options = '--with-arch=armv7-a --with-fpu=vfp --with-thumb --without-intl-api'

add_config('armsim',       None, '--enable-arm-simulator')
add_config('nounified',    None, '--disable-unified-compilation')
add_config('noion',        None, '--disable-ion')
add_config('gctrace',      None, '--enable-gc-trace')
add_config('valgrind',     None, '--enable-valgrind')

add_config('noggc',        'gc', '--disable-gcgenerational')
add_config('conservative', 'gc', '--disable-exact-rooting --disable-gcgenerational')
add_config('cgc',          'gc', '--enable-gccompacting')

add_config('debug',        'opt', ('--enable-gczeal --enable-js-diagnostics ' +
                                  '--enable-debug --disable-optimize'))
add_config('optdebug',     'opt', ('--enable-gczeal --enable-js-diagnostics ' +
                                  '--enable-debug --enable-optimize'))
add_config('opt',          'opt', '--disable-debug --enable-optimize')
config_group_defaults['opt'] = 'debug'

add_config('clang',        'compiler', None, 'clang', 'clang++')
add_config('gcc',          'compiler', None, 'gcc', 'g++')
add_config('gcc47',        'compiler', None, 'gcc-4.7', 'g++-4.7')
add_config('gcc32',        'compiler', '--target=i686-pc-linux', 'gcc -m32', 'g++ -m32',
           { 'PKG_CONFIG_LIBDIR': '/usr/lib/pkgconfig', 'AR': 'ar' })
add_config('armsf',        'compiler',
           arm_options + ' --target=arm-linux-gnueabi --with-float-abi=softfp',
           'arm-linux-gnueabi-gcc', 'arm-linux-gnueabi-g++')
add_config('armhf',        'compiler',
           arm_options + ' --target=arm-linux-gnueabihf --with-float-abi=hard',
           'arm-linux-gnueabihf-gcc', 'arm-linux-gnueabihf-g++')
config_group_defaults['compiler'] = 'clang'


# todo: --with-system-nspr doesn't work with crosscompilation, because
# it tries to link with the host library
common_options = '--with-ccache=`which ccache` --with-system-nspr --enable-ctypes'

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

    # Check for mutally exclusive configs
    config_groups_specified = {}
    for config in configs:
        assert config in config_names
        group = config_group[config]
        if group:
            if group in config_groups_specified:
                sys.exit("Config %s conflicts with previous config %s" %
                         (config, config_groups_specified[group]))
            config_groups_specified[group] = config

    # Add config group defaults
    for group in config_group_defaults.keys():
        if group not in config_groups_specified:
            configs.append(config_group_defaults[group])

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
