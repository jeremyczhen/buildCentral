"""
/*
 * Copyright (C) 2015   Jeremy Chen jeremy_cz@yahoo.com
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
"""

import simplejson as json
import networkx as nx
import os
from string import Template
import subprocess as sp
import shutil
import tarfile
import copy
import platform
import multiprocessing
import shlex

build_all_target = '__all__' 
build_cmd_pipe = None
build_stop = None

cmake_generator = {
        'vs16'      : 'Visual Studio 16 2019',
        'vs15'      : 'Visual Studio 15 2017',
        'vs14'      : 'Visual Studio 14 2015',
        'vs12'      : 'Visual Studio 12 2013',
        'vs11'      : 'Visual Studio 11 2012',
        'vs10'      : 'Visual Studio 10 2010',
        'vs9'       : 'Visual Studio 9 2008',
        'nmake'     : 'NMake Makefiles',
        'gh'        : 'Green Hills MULTI',
        'mingw'     : 'MinGW Makefiles',
        'unix'      : 'Unix Makefiles',
        'emingw'    : 'Eclipse CDT4 - MinGW Makefiles',
        'enmake'    : 'Eclipse CDT4 - NMake Makefiles',
        'eunix'     : 'Eclipse CDT4 - Unix Makefiles'
        }

def guess_project_root():
    signature = set(['external', 'workspace', 'project', 'tools'])
    cwd = cur_dir = os.getcwd()
    parent_dir = os.path.abspath(os.path.join(cur_dir, os.pardir))
    while (parent_dir != cur_dir):
        if signature.issubset(set(os.listdir(cur_dir))):
            break
        cur_dir = parent_dir
        parent_dir = os.path.abspath(os.path.join(cur_dir, os.pardir))
    if os.path.dirname(os.path.realpath(cur_dir)) == cur_dir:
        print('Cannot fild project root! using curent directory instead.')
        cur_dir = cwd
    return cur_dir

def do_import_build_group(group_name, group_config, packages):
    if not group_name in group_config:
        return 'Group %s is not found!'%(group_name)
    group = group_config[group_name]

    if 'BASE' in group:
        for group_name in group['BASE']:
            ret = do_import_build_group(group_name, group_config, packages)
            if ret != 'ok':
                return ret

    if 'PACKAGES' in group:
        packages['PKG'] = packages['PKG'] | set(group['PACKAGES'])
    return 'ok'

def init_private_config(config):
    config['private'] = {}
    for arch in config['TARGET_LIST']:
        config['private'][arch] = {'toolchain_root' : '',
                                   'c_compiler' : '',
                                   'cxx_compiler' : '',
                                   'asm_compiler' : '',
                                   'archiver' : '',
                                   'toolchain_file' : '',
                                   'sys_root' : [],
                                   'compiler_type' : '',
                                   'target_arch' : '',
                                   'target_os' : '',
                                   'cmake_generator' : '',
                                   'c_flags' : '',
                                   'cxx_flags' : '',
                                   'asm_flags' : '',
                                   'release_flags' : '',
                                   'debug_flags' : '',
                                   'macro_definition' : {},
                                   'make_var' : {},
                                   'shared_ld_flags' : '',
                                   'exe_ld_flags' : '',
                                   'ld_flags' : '',
                                   'lib_search_path' : [],
                                   'head_search_path' : [],
                                   'env_var' : {},
                                   'stage_dir' : '',
                                   'env_source_cmd' : ''
                                   }

def import_configs(dst, src):
    for item in src:
        src_value = src[item]
        if item == 'TOOLCHAIN':
            dst['toolchain_root'] =  os.path.normpath(os.path.expanduser(src_value))
        elif item == 'TOOLCHAIN_CC':
            dst['c_compiler'] = os.path.normpath(os.path.expanduser(src_value))
        elif item == 'TOOLCHAIN_CXX':
            dst['cxx_compiler'] = os.path.normpath(os.path.expanduser(src_value))
        elif item == 'TOOLCHAIN_ASM':
            dst['asm_compiler'] = os.path.normpath(os.path.expanduser(src_value))
        elif item == 'TOOLCHAIN_AR':
            dst['archiver'] = os.path.normpath(os.path.expanduser(src_value))
        elif item == 'SYSROOT':
            dst['sys_root'] =  [os.path.normpath(os.path.expanduser(x)) for x in src_value]
        elif item == 'COMPILER_TYPE':
            dst['compiler_type'] = src_value
        elif item == 'TARGET_ARCH':
            dst['target_arch'] = src_value
        elif item == 'TARGET_OS':
            dst['target_os'] = src_value
        elif item == 'TOOLCHAIN_FILE':
            dst['toolchain_file'] = src_value 
        elif item == 'STAGE_DIR':
            dst['stage_dir'] = src_value
        elif item == 'CMAKE_GENERATOR':
            generator = src_value
            if (generator in cmake_generator):
                dst['cmake_generator'] = generator 
            else:
                return {'ret' : 'error', 'info' : 'unknown generator %s!'%(generator)}
        elif item == 'ENV_SOURCE_CMD':
            dst['env_source_cmd'] = src_value
        elif item == 'MACRO_DEF':
            dst['macro_definition'].update(src_value)
        elif item == 'MAKE_VAR':
            dst['make_var'].update(src_value)
        elif item == 'C_FLAGS':
            dst['c_flags'] += src_value + ' '
        elif item == 'CXX_FLAGS':
            dst['cxx_flags'] += src_value + ' '
        elif item == 'ASM_FLAGS':
            dst['asm_flags'] += src_value + ' '
        elif item == 'REL_FLAGS':
            dst['release_flags'] += src_value + ' '
        elif item == 'DBG_FLAGS':
            dst['debug_flags'] += src_value + ' '
        elif item == 'SHA_LD_FLAGS':
            dst['shared_ld_flags'] += src_value + ' '
        elif item == 'EXE_LD_FLAGS':
            dst['exe_ld_flags'] += src_value + ' '
        elif item == 'OTHER_LIB_PATH':
            dst['lib_search_path'] += [os.path.normpath(os.path.expanduser(x)) for x in src_value]
        elif item == 'OTHER_INC_PATH':
            dst['head_search_path'] += [os.path.normpath(os.path.expanduser(x)) for x in src_value]
        elif item == 'LD_FLAGS':
            dst['ld_flags'] += src_value + ' '
        elif item == 'ENV_VAR':
            dst['env_var'].update(src_value)

    return {'ret' : 'ok', 'info' : None}

def do_import_private_config(config, cfg_file):
    try:
        fd = open(cfg_file)
    except IOError:
        return {'ret' : 'ok', 'info' : 'Warning: %s does not exists!'%(cfg_file)}
    """
    try:
        private_cfg = json.loads(fd.read())
    except ValueError as e:
        fd.close()
        return {'ret' : 'error', 'info' : '%s: Config file %s is not in json format!'%(str(e), cfg_file)}
    fd.close()
    """
    template = Template(fd.read())
    fd.close()
    try:
        private_cfg = json.loads(template.substitute(PROOT = config['proj_root'].replace('\\', '/')))
    except ValueError as e:
        return {'ret' : 'error', 'info' : '%s: Config file %s is not in json format!'%(str(e), cfg_file)}

    for arch in private_cfg:
        if arch in config['TARGET_LIST']:
            ret = import_configs(config['private'][arch], private_cfg[arch])
            if ret['ret'] != 'ok':
                return ret

            if not config['private'][arch]['target_arch']:
                return {'ret' : 'error', 'info' : 'TARGET_ARCH is not defined for %s!'%(arch)}
            if not config['private'][arch]['target_os']:
                return {'ret' : 'error', 'info' : 'TARGET_OS is not defined for %s!'%(arch)}

    return {'ret' : 'ok', 'info' : None}

def import_private_config(config):
    init_private_config(config)
    files = [
             # default config
             os.path.join(config['proj_root'], 'tools', 'buildCentral', 'rules', 'buildcentralrc'),
             # project specific config
             os.path.join(config['proj_root'], 'project', 'build', 'buildcentralrc'),
             # private config
             os.path.join(os.path.expanduser('~'), '.buildcentralrc')
            ]

    for cfg_file in files:
        ret = do_import_private_config(config, os.path.expanduser(cfg_file))
        if ret['ret'] != 'ok':
            return ret

    for arch in config['TARGET_LIST']:
        if not arch in config['private']:
            return {'ret' : 'error', 'info' : 'Arch %s is specified but not configured!'%(arch)}

    return {'ret' : 'ok', 'info' : None}

def arch_is_host(arch, config):
    if arch ==  config['os_type']:
        return True
    else:
        return False

def get_stage_path(config, arch, variant, output_dir = None):
    if not output_dir:
        output_dir = config.get('OUTPUT_DIR', '')
    if config['private'][arch]['stage_dir']:
        path = config['private'][arch]['stage_dir']
    else:
        if arch_is_host(arch, config):
            # no variant for host build
            path = os.path.join(output_dir, 'stage', config['HOST'])
        else:
            path = os.path.join(output_dir, 'stage', variant, arch)
    return path

def config_package_path(config, arch, pkg, variant):
    src_path = os.path.abspath(os.path.join(config['proj_root'], config['PACKAGES'][arch][pkg]['Path']))
    output_dir = config.get('OUTPUT_DIR', src_path)
    if os.path.isfile(src_path):
        config['PACKAGES'][arch][pkg]['Path'] = os.path.join(output_dir,
                                                             config['PACKAGES'][arch][pkg]['Path'])
    else:
        config['PACKAGES'][arch][pkg]['Path'] = src_path

    config['PACKAGES'][arch][pkg]['BuildDir'] = os.path.join(output_dir, 'build', variant, pkg, arch)
    config['PACKAGES'][arch][pkg]['StageDir'] = get_stage_path(config, arch, variant, output_dir)

'''
def parse_build_order(package_list, graphs):
    ordered_packages = []
    for i in range(len(package_list)):
        packages = package_list[i]
        graph = graphs[i]
        dep_list = []
        for package in packages:
            generate_build_order(graph, package, dep_list)
        ordered_packages.append(dep_list)

    pkg_set = set(ordered_packages)
    if build_all_target in ordered_packages:
        ordered_packages.remove(build_all_target)
    ordered_packages = list(ordered_packages)
    ordered_packages.append(build_all_target)
    return ordered_packages
'''

def load_build_config(cfg_dir, proj_root):
    config = {'ret' : 'ok'}
    if not proj_root:
        proj_root = guess_project_root()
    config['proj_root'] = proj_root

    config['platform_info'] = platform.uname()
    os_name = config['platform_info'][0]
    host_arch = None
    if 'Windows' in os_name:
        host_arch = 'windows'
    elif 'Linux' in os_name:
        host_arch = 'linux'
    elif 'CYGWIN' in os_name:
        host_arch = 'cygwin'

    if host_arch:
        config['os_type'] = host_arch
    else:
        config['ret'] = 'Unknown OS: %s'%(os_name)
        return config

    if cfg_dir:
        cfg_file = os.path.join(cfg_dir, 'build_central.cfg')
    else:
        cfg_file = os.path.join(proj_root, 'project', 'build', 'build_central.cfg')
    try:
        fd = open(cfg_file, 'r')
    except IOError:
        config['ret'] = 'Cannot open config file: %s!'%(cfg_file)
        return config
    else:
        template = Template(fd.read())
        fd.close()
        try:
            origin_cfg = json.loads(template.substitute(PROOT = proj_root.replace('\\', '/')))
        except ValueError as e:
            config['ret'] = '%s: Config file %s is not in json format!'%(str(e), cfg_file)
            return config
        """
        tmp = fd.read()
        fd.close()
        try:
            origin_cfg = json.loads(tmp)
        except ValueError as e:
            config['ret'] = '%s: Config file %s is not in json format!'%(str(e), cfg_file)
            return config
        """

        config['PROJECT_NAME'] = origin_cfg.get('PROJECT_NAME', None)
        config['LOGO'] = origin_cfg.get('LOGO', None)

        config['HOST'] = origin_cfg.get('HOST', None)
        if 'TARGETS' in origin_cfg:
            config['TARGET_LIST'] = origin_cfg['TARGETS']
        else:
            config['ret'] = 'TARGETS should be defined!'
            return config
        if 'DEFAULT_TARGET' in origin_cfg:
            config['DEFAULT_TARGET'] = origin_cfg['DEFAULT_TARGET']
            if not config['DEFAULT_TARGET'] in config['TARGET_LIST']:
                config['ret'] = 'Invalid DEFAULT_TARGET!'
                return config
        else:
            config['ret'] = 'DEFAULT_TARGET should be defined!'
            return config
        if 'BUILD_VARIANTS' in origin_cfg:
            config['BUILD_VARIANTS'] = origin_cfg['BUILD_VARIANTS']
            for arch in config['BUILD_VARIANTS']:
                if not arch in config['TARGET_LIST']:
                    config['ret'] = 'Error! arch %s in BUILD_VARIANTS is invalid!'%(arch)
                    return config
                if not config['BUILD_VARIANTS'][arch]["DEFAULT_VARIANT"] in config['BUILD_VARIANTS'][arch]["VARIANTS"]:
                    config['ret'] = 'Error! DEFAULT_VARIANT for %s is not found in BUILD_VARIANTS.arch.VARIANTS'%(arch)
                    return config
        else:
            config['ret'] = 'BUILD_VARIANTS should be defined!'
            return config

        ret = import_private_config(config)
        if ret['ret'] != 'ok':
            config['ret'] = ret['info']
            return config

        config['OUTPUT_DIR'] = os.path.normpath(os.path.expanduser(
                               origin_cfg.get('OUTPUT_DIR', os.path.join(proj_root, 'output'))))
        config['LOG_DIR'] = os.path.join(config['OUTPUT_DIR'], 'log')

        config['PACKAGES'] = {}
        if 'PACKAGES'in origin_cfg:
            for arch in config['TARGET_LIST']:
                config['PACKAGES'][arch] = copy.deepcopy(origin_cfg['PACKAGES'])
        else:
            for arch in config['TARGET_LIST']:
                config['PACKAGES'][arch] = {}

        if 'PACKAGES-PER-ARCH'in origin_cfg:
            config['PACKAGES-PER-ARCH'] = {} 
            for arch in origin_cfg['PACKAGES-PER-ARCH']:
                if not arch in config['TARGET_LIST']:
                    config['ret'] = 'Error! arch %s in PACKAGES-PER-ARCH tag is invalid!'%(arch)
                    return config
                config['PACKAGES-PER-ARCH'][arch] = copy.deepcopy(origin_cfg['PACKAGES-PER-ARCH'][arch])
                for pkg in origin_cfg['PACKAGES-PER-ARCH'][arch]:
                    if not pkg in config['PACKAGES'][arch]:
                        config['PACKAGES'][arch][pkg] = {}

                    path = origin_cfg['PACKAGES-PER-ARCH'][arch][pkg].get('Path', None)
                    if not path is None:
                        config['PACKAGES'][arch][pkg]['Path'] = path
                    dep = origin_cfg['PACKAGES-PER-ARCH'][arch][pkg].get('Dependency', None)
                    if not dep is None:
                        config['PACKAGES'][arch][pkg]['Dependency'] = list(set(dep))
                    target = origin_cfg['PACKAGES-PER-ARCH'][arch][pkg].get('MakeTarget', None)
                    if not target is None:
                        config['PACKAGES'][arch][pkg]['MakeTarget'] = target 
                    tools = origin_cfg['PACKAGES-PER-ARCH'][arch][pkg].get('Tools', None)
                    if not tools is None:
                        config['PACKAGES'][arch][pkg]['Tools'] = tools

        for arch in config['PACKAGES']:
            for pkg in config['PACKAGES'][arch]:
                if 'Tools' in config['PACKAGES'][arch][pkg]:
                    config['PACKAGES'][arch][pkg]['Tools'] = set(config['PACKAGES'][arch][pkg]['Tools'])

        for arch in config['BUILD_VARIANTS']:
            for variant in config['BUILD_VARIANTS'][arch]['VARIANTS']:
                config['BUILD_VARIANTS'][arch]['VARIANTS'][variant]['GRAPHS'] = []
                config['BUILD_VARIANTS'][arch]['VARIANTS'][variant]['PACKAGES'] = []

                for group_name in config['BUILD_VARIANTS'][arch]['VARIANTS'][variant]['GROUPS']:
                    packages = {'PKG' : set()}
                    ret = do_import_build_group(group_name, origin_cfg['GROUPS'], packages)
                    if ret != 'ok':
                        config['ret'] = 'Error parsing BUILD_VARIANTS.%s.VARIANTS.%s: %s'%(arch, variant, ret)
                        return config

                    package_list = packages['PKG']
                    for pkg in list(package_list):
                        if 'Tools' in config['PACKAGES'][arch][pkg]:
                            if arch_is_host(arch, config) and pkg != dep_pkg:
                                package_list |= set(config['PACKAGES'][arch][pkg]['Tools'])

                        if 'Dependency' in config['PACKAGES'][arch][pkg]:
                            package_list |= set(config['PACKAGES'][arch][pkg]['Dependency'])

                    config['BUILD_VARIANTS'][arch]['VARIANTS'][variant]['PACKAGES'].append(list(package_list))

                    graph =  nx.DiGraph()
                    for pkg in package_list:
                        if not pkg in config['PACKAGES'][arch]:
                            config['ret'] = 'Arch: %s: Package %s is not defined in PACKAGE in file %s!'%(arch, pkg, cfg_file)
                            return config

                        if 'Tools' in config['PACKAGES'][arch][pkg]:
                            for dep_pkg in config['PACKAGES'][arch][pkg]['Tools']:
                                if not dep_pkg in config['PACKAGES'][host_arch]:
                                    config['ret'] = 'Arch: %s, Tool %s is not defined for host %s in file %s!'%(arch, dep_pkg, host_arch, cfg_file)
                                    return config
                                if arch_is_host(arch, config) and pkg != dep_pkg:
                                    graph.add_edge(pkg, dep_pkg)

                        if 'Dependency' in config['PACKAGES'][arch][pkg]:
                            for dep_pkg in config['PACKAGES'][arch][pkg]['Dependency']:
                                if not dep_pkg in config['PACKAGES'][arch]:
                                    config['ret'] = 'Arch: %s, Package %s is not defined in Dependency in file %s!'%(arch, dep_pkg, cfg_file)
                                    return config
                                graph.add_edge(pkg, dep_pkg)

                    #for pkg in graph:
                    #    if not pkg in origin_cfg['GROUPS'][arch][group]['PACKAGES']:
                    #        print('File %s, arch %s, Group %s: package %s is depended but not list for build!'%(cfg_file, arch, group, pkg))
                    #        pass

                    loop_str = ''
                    for loop in nx.simple_cycles(graph):
                        loop_str += str(loop) + ', '

                    if loop_str:
                        config['ret'] = 'File %s, arch %s: Loop dependency is found: %s!'%(cfg_file, arch, str(loop))
                        return config

                    root_pkg = []
                    #for pkg, degree in graph.in_degree().items():
                    try:
                        in_degree = graph.in_degree().items()
                    except:
                        in_degree = graph.in_degree()
                    for pkg, degree in in_degree:
                        if degree == 0:
                            root_pkg.append(pkg)
                    for pkg in root_pkg:
                        graph.add_edge(build_all_target, pkg)

                    for pkg in package_list:
                        if not pkg in graph:
                            graph.add_edge(build_all_target, pkg)

                    config['BUILD_VARIANTS'][arch]['VARIANTS'][variant]['GRAPHS'].append(graph)

    host_stage_dir = os.path.join(config['OUTPUT_DIR'], 'stage', config['HOST'])
    config['tool_path'] = (os.path.join(config['proj_root'], 'tools', 'bin', config['os_type']),
            os.path.join(host_stage_dir, 'bin'),
            os.path.join(host_stage_dir, 'usr', 'bin'))
    config['tool_lib'] = (os.path.join(config['proj_root'], 'tools', 'lib', config['os_type']),
            os.path.join(host_stage_dir, 'lib'),
            os.path.join(host_stage_dir, 'usr', 'lib'))

    return config

def add_definition(cmd, var, value = None):
    if value is None:
        cmd += ['-D' + var]
    else:
        cmd += ['-D' + var + '=' + value]

source_env_cache = {}
def load_env_from_source_file(source_file):
    global source_env_cache
    env = {}

    if not source_file:
        return env

    if source_file in source_env_cache:
        return source_env_cache[source_file]

    #command = shlex.split("env -i bash -c ' " + source_file + " && env '")
    command = shlex.split("bash -c ' " + source_file + " && env'")
    proc = sp.Popen(command, stdout = sp.PIPE)
    for line in proc.stdout:
        line = str(line)
        (key, _, value) = line.partition('=')
        env[key] = value.rstrip()
    proc.communicate()
    source_env_cache[source_file] = env
    return env

def setup_global_build_env(arch, config):
    if config['tool_path']:
        pathes = os.pathsep.join(config['tool_path'])
        env = os.getenv('PATH')
        if env:
            env += os.pathsep + pathes
        else:
            env = pathes
        os.putenv('PATH', env)

    if config['tool_lib']:
        pathes = os.pathsep.join(config['tool_lib'])
        env = os.getenv('LD_LIBRARY_PATH')
        if env:
            env += os.pathsep + pathes
        else:
            env = pathes
        os.putenv('LD_LIBRARY_PATH', env)

def get_generator_id(generator, arch, config):
    if not generator:
        if arch in config['private']:
            if config['private'][arch]['cmake_generator']:
                generator = config['private'][arch]['cmake_generator']
    if not generator:
        generator = 'eunix'
        if config['os_type'] == 'windows':
            if arch_is_host(arch, config) or arch == 'rh850':
                generator = 'nmake'
    return generator

def check_generator(generator, arch, config):
    return cmake_generator[get_generator_id(generator, arch, config)]

def get_build_cmd_type(package, arch, config):
    cmd_type = 'unknown'
    package_base = config['PACKAGES'][arch][package]['Path']
    if os.path.exists(os.path.join(package_base, 'CMakeLists.txt')): 
        cmd_type = 'cmake'
    elif os.path.exists(os.path.join(package_base, 'Makefile')) or os.path.exists(os.path.join(package_base, 'GNUMakefile')): 
        cmd_type = 'make'
    return cmd_type

def create_build_command(package, arch, variant, debug, verbose, stage, nr_jobs, generator, cmd_type, config, private_config, cmd):
    sys_root = private_config['sys_root']
    stage_root = config['PACKAGES'][arch][package]['StageDir']
    if stage_root:
        sys_root += [stage_root]

    make_var = private_config['make_var']
    macro_var = private_config['macro_definition']
    lib_pathes = private_config['lib_search_path']
    head_pathes = private_config['head_search_path']

    if get_generator_id(generator, arch, config) == 'nmake':
        make_tool = ['nmake']
        make_tool_with_job = ['nmake']
    else:
        make_tool = ['make']
        make_tool_with_job = ['make', '-j', str(nr_jobs)]

    package_base = config['PACKAGES'][arch][package]['Path']
    make_target = config['PACKAGES'][arch][package]['MakeTarget']
    if cmd_type == 'cmake':
        # if exists 'CMakeLists.txt', cmake it;
        private_config['env_var']['C_COMPILER'] = private_config['c_compiler']
        private_config['env_var']['CXX_COMPILER'] = private_config['cxx_compiler']
        if stage == 'clean':
            cmd += make_tool +  ['clean']
        elif stage == 'cmake':
            cmd += ['cmake']
            add_definition(cmd, 'PROJECT_ROOT', config['proj_root'])
            rule_dir = os.path.join(config['proj_root'], 'tools', 'buildCentral', 'rules')
            add_definition(cmd, 'RULE_DIR', rule_dir)
            if not arch_is_host(arch, config):
                toolchain_file = private_config['toolchain_file']
                if not toolchain_file:
                    toolchain_file = os.path.join(rule_dir, 'toolchain.cmake')
                add_definition(cmd, 'CMAKE_TOOLCHAIN_FILE', toolchain_file)
            if debug:
                add_definition(cmd, 'CMAKE_BUILD_TYPE', 'Debug')
            else:
                add_definition(cmd, 'CMAKE_BUILD_TYPE', 'Release')

            generator = check_generator(generator, arch, config) 
            cmd.append('-G')
            cmd.append(generator)

            if make_var:
                v = [i + '=' + make_var[i] for i in make_var]
                for d in v:
                    add_definition(cmd, d)

            if macro_var:
                m = [i + '=' + macro_var[i] if macro_var[i] else i for i in macro_var]
                add_definition(cmd, 'MACRO_DEF', ';'.join(m))

            build_macro = config['BUILD_VARIANTS'][arch]['VARIANTS'][variant].get('MACRO', None)
            if build_macro:
                add_definition(cmd, 'MACRO_VARIANT', build_macro)

            if private_config['toolchain_root']:   add_definition(cmd, 'TOOL_ROOT',        private_config['toolchain_root'])
            if private_config['compiler_type']:    add_definition(cmd, 'COMPILER_TYPE',    private_config['compiler_type'])
            if private_config['target_arch']:      add_definition(cmd, 'TARGET_ARCH',      private_config['target_arch'])
            if private_config['target_os']:        add_definition(cmd, 'TARGET_OS',        private_config['target_os'])
            if private_config['archiver']:         add_definition(cmd, 'CMAKE_AR',         private_config['archiver'])
            if private_config['c_flags']:          add_definition(cmd, 'CMAKE_C_FLAGS',    private_config['c_flags'])
            if private_config['asm_compiler']:     add_definition(cmd, 'CMAKE_ASM_COMPILER', private_config['asm_compiler'])
            if private_config['asm_flags']:        add_definition(cmd, 'CMAKE_ASM_FLAGS',  private_config['asm_flags'])
            if private_config['cxx_flags']:        add_definition(cmd, 'CMAKE_CXX_FLAGS',  private_config['cxx_flags'])
            if private_config['release_flags']:    add_definition(cmd, 'REL_FLAGS',        private_config['release_flags'])
            if private_config['debug_flags']:      add_definition(cmd, 'DBG_FLAGS',        private_config['debug_flags'])
            ld_flags = private_config['ld_flags']
            if  private_config['shared_ld_flags']: ld_flags += ' ' + private_config['shared_ld_flags']
            if ld_flags: add_definition(cmd, 'CMAKE_SHARED_LINKER_FLAGS', ld_flags)
            ld_flags =  private_config['ld_flags']
            if private_config['exe_ld_flags']: ld_flags += ' ' + private_config['exe_ld_flags']
            if ld_flags: add_definition(cmd, 'CMAKE_EXE_LINKER_FLAGS', ld_flags)
            if lib_pathes:                         add_definition(cmd, 'LIB_PATH',        ';'.join(lib_pathes))
            if head_pathes:                        add_definition(cmd, 'INC_PATH',        ';'.join(head_pathes))

            if verbose:
                add_definition(cmd, 'CMAKE_VERBOSE_MAKEFILE', 'on')
            else:
                add_definition(cmd, 'CMAKE_VERBOSE_MAKEFILE', 'off')

            if stage_root:
                add_definition(cmd, 'CMAKE_INSTALL_PREFIX', stage_root)
            if sys_root:
                add_definition(cmd, 'SYSTEM_ROOT', ';'.join(sys_root))

            add_definition(cmd, 'PROJECT_ROOT', config['proj_root'])

            definitions = config.get('extra_make_var')
            if definitions:
                for item in definitions:
                    cmd += ['-D' + item]

            add_definition(cmd, 'PACKAGE_NAME', package)
            cmd.append(package_base)
        elif stage == 'make':
            generator = check_generator(generator, arch, config) 
            if 'Visual Studio' in generator:
                cmd = []
            else:
                cmd += make_tool_with_job
                if make_target:
                    cmd += [make_target]
        elif stage == 'uninstall':
            cmd += make_tool + ['uninstall']
    elif cmd_type == 'make':
        # if exists 'Makefile' or 'GNUMakefile', make it;
        if stage == 'clean':
            cmd += make_tool + ['clean']
        elif stage == 'make':
            cmd += make_tool_with_job
            if make_target:
                cmd += [make_target]
            if stage_root:
                cmd += ['DESTDIR='+stage_root]
        elif stage == 'uninstall':
            cmd += make_tool + ['uninstall']
        else:
            return[]

        if private_config['c_compiler']:
            cmd += ['CC=' + private_config['c_compiler']]
        if private_config['c_compiler']:
            cmd += ['CXX=' + private_config['cxx_compiler']]

        cflags = ''
        cxxflags = ''
        if sys_root:
            pathes = ['-I' + os.path.normpath(os.path.expanduser(os.path.join(p, 'include'))) for p in sys_root]
            inc_path = ' '.join(pathes)
            cflags += ' ' + inc_path
            cxxflags += ' ' + inc_path
            pathes = ['-I' + os.path.normpath(os.path.expanduser(os.path.join(p, 'usr', 'include'))) for p in sys_root]
            inc_path = ' '.join(pathes)
            cflags += ' ' + inc_path
            cxxflags += ' ' + inc_path
        if head_pathes:
            pathes = ['-I' + os.path.normpath(os.path.expanduser(p)) for p in head_pathes]
            inc_path = ' '.join(pathes)
            cflags += ' ' + inc_path
            cxxflags += ' ' + inc_path
        if macro_var:
            macro = ''
            macro_def = ['-D' + i + '=' + macro_var[i] if macro_var[i] else '-D' + i for i in macro_var]
            macro = ' '.join(macro_def)
            cflags += ' ' + macro
            cxxflags += ' ' + macro 
        if private_config['c_flags']:
            cflags += ' ' + private_config['c_flags']
        if private_config['cxx_flags']:
            cxxflags += ' ' + private_config['cxx_flags']

        ldflags = ''
        if sys_root:
            pathes = ['-L' + os.path.normpath(os.path.expanduser(os.path.join(p, 'lib'))) for p in sys_root]
            ldflags = ' ' + ' '.join(pathes) 
            pathes = ['-L' + os.path.normpath(os.path.expanduser(os.path.join(p, 'usr', 'lib'))) for p in sys_root]
            ldflags = ' ' + ' '.join(pathes) 
        if lib_pathes:
            pathes = ['-L' + os.path.normpath(os.path.expanduser(p)) for p in lib_pathes]
            ldflags = ' ' + ' '.join(pathes)
        if private_config['ld_flags']:
            ldflags += ' ' + private_config['ld_flags']

        if not private_config['env_source_cmd']:
            if cflags:
                cmd += ['CFLAGS=' + cflags]
            if cxxflags:
                cmd += ['CXXFLAGS=' + cxxflags]
            if ldflags:
                cmd += ['LDFLAGS=' + ldflags]

        variables = []
        if make_var:
            variables = [i + '=' + make_var[i] for i in make_var]
        extra_var = config.get('extra_make_var')
        if extra_var:
            variables += extra_var
        if variables:
            cmd += [' '.join(variables)]

    cmd = shlex.split(' '.join(cmd))
    print(cmd)
    return private_config

def figure_out_build_order(G, package, build_list):
    idx = build_list.index(package)
    for neighbor in G.neighbors(package):
        if neighbor in build_list[0:idx]:
            del(build_list[build_list.index(neighbor)])
            build_list.insert(build_list.index(package) + 1, neighbor)
        elif not neighbor in build_list[idx:]:
            build_list.append(neighbor)

    for neighbor in G.neighbors(package):
        figure_out_build_order(G, neighbor, build_list)

def generate_build_order_for_single_graph(G, package, build_list):
    if not package in build_list:
        build_list.append(package)
        figure_out_build_order(G, package, build_list)

def generate_all_build_order(graphs, build_list):
    ordered_packages = []
    for graph in graphs:
        bp = []
        generate_build_order_for_single_graph(graph, build_all_target, bp)
        bp.reverse()
        [ordered_packages.append(i) for i in bp if not i in ordered_packages]
 
    ordered_packages.reverse()
    if build_all_target in ordered_packages:
        ordered_packages.remove(build_all_target)
    [build_list.append(i) for i in ordered_packages if not i in build_list]

def generate_build_order(graphs, package, build_list):
    if package == build_all_target:
        generate_all_build_order(graphs, build_list)
    else:
        for graph in graphs:
            if not package in graph:
                continue
            generate_build_order_for_single_graph(graph, package, build_list)

def get_tools(config, arch, packages):
    tools = set()
    for pkg in packages:
        if pkg != build_all_target and 'Tools' in config['PACKAGES'][arch][pkg]:
            tools = tools | (config['PACKAGES'][arch][pkg]['Tools'] - tools)
    return tools

def should_install(config, arch, package):
    target = config['PACKAGES'][arch][package].get('MakeTarget', None)
    return target and target == 'install'

def setup_env(env_list):
    os.environ.update(env_list)

def unset_env(env_list):
    for env in env_list:
        if env in os.environ:
            del os.environ[env]

def do_build_packages(packages, arch, variant, debug, verbose, clean, not_build, nr_jobs, generator, config, output):
    global build_stop
    global build_cmd_pipe

    if not variant:
        variant = config['BUILD_VARIANTS'][arch]['DEFAULT_VARIANT']

    if not nr_jobs:
        nr_jobs = multiprocessing.cpu_count()
    cur_package = '' 
    build_stop = 0
    ret = 'ok'
    log_base = os.path.join(config['LOG_DIR'], arch)
    if not os.path.exists(log_base):
        try:
            os.makedirs(log_base)
        except:
            return {'info' : 'Unable to create log dir %s'%(log_base), 'package' : None}
    log_fd = open(os.path.join(log_base, 'log'), 'wb')
    if build_all_target in packages:
        del(packages[packages.index(build_all_target)])

    if nr_jobs < 1:
        nr_jobs = 1

    pkg_cfg = {}
    for pkg in packages:
        cfg = copy.deepcopy(config['private'][arch])
        import_configs(cfg, config['PACKAGES'][arch][pkg])
        if 'PACKAGES-PER-ARCH' in config and arch in config['PACKAGES-PER-ARCH'] and pkg in config['PACKAGES-PER-ARCH'][arch]:
            import_configs(cfg, config['PACKAGES-PER-ARCH'][arch][pkg])
        cfg['env_var'].update(load_env_from_source_file(cfg['env_source_cmd'])) 
        pkg_cfg[pkg] = cfg

    setup_global_build_env(arch, config)
    # ==== Clean packages ====
    if clean:
        for pkg in packages:
            config_package_path(config, arch, pkg, variant)
            cur_package = pkg
            cmd_type = get_build_cmd_type(pkg, arch, config)

            if cmd_type == 'cmake':
                work_path = config['PACKAGES'][arch][pkg]['BuildDir']
            else:
                work_path = config['PACKAGES'][arch][pkg]['Path']

            def setup_environment():
                os.chdir(work_path)
                setup_env(pkg_cfg[pkg]['env_var'])

            env_set = False 
            if os.path.exists(work_path):
                try:
                    if clean == 'uninstall_clean' and should_install(config, arch, pkg):
                        cmd = []
                        create_build_command(pkg, arch, variant, debug, verbose, 'uninstall',
                                                   nr_jobs, generator, cmd_type, config, pkg_cfg[pkg], cmd)
                        if cmd:
                            if config['os_type'] == 'windows':
                                env_set = True 
                                setup_environment()
                                build_cmd_pipe = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.STDOUT)
                            else:
                                build_cmd_pipe = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.STDOUT, preexec_fn = setup_environment)
                            while True:
                                line = build_cmd_pipe.stdout.readline()
                                if not line: break
                                output(line)
                                log_fd.write(line)
                                if build_stop:
                                    break
                            if build_stop:
                                break
                except:
                    pass

                try:
                    if clean == 'uninstall_clean' or clean == 'clean_only':
                        cmd = []
                        create_build_command(pkg, arch, variant, debug, verbose, 'clean',
                                             nr_jobs, generator, cmd_type, config, pkg_cfg[pkg], cmd)
                        if cmd:
                            if config['os_type'] == 'windows':
                                if not env_set:
                                    env_set = True
                                    setup_environment()
                                build_cmd_pipe = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.STDOUT)
                            else:
                                build_cmd_pipe = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.STDOUT, preexec_fn = setup_environment)
                            while True:
                                line = build_cmd_pipe.stdout.readline()
                                if not line: break
                                output(line)
                                log_fd.write(line)
                                if build_stop:
                                    break
                            if build_stop:
                                break

                except:
                    pass
                try:
                    if cmd_type == 'cmake':
                        print('Removing working directory: ' + work_path)
                        shutil.rmtree(work_path, ignore_errors=True)
                except:
                    pass

                if build_stop:
                    break

            if env_set:
                env_set = False
                unset_env(pkg_cfg[pkg]['env_var'])

    if not_build:
        return {'info' : ret, 'package' : None}

    # ==== Build packages ====
    env_set = False
    try:
        for pkg in packages:
            config_package_path(config, arch, pkg, variant)
            cur_package = pkg
            cmd_type = get_build_cmd_type(pkg, arch, config)
            if cmd_type == 'cmake':
                work_path = config['PACKAGES'][arch][pkg]['BuildDir']
                if not os.path.exists(work_path):
                    try:
                        os.makedirs(work_path)
                    except:
                        return {'info' : 'Package %s: cannot create work path %s!'%s(pkg, work_path)}
            elif cmd_type == 'make':
                work_path = config['PACKAGES'][arch][pkg]['Path']
                if not os.path.exists(work_path):
                    ret = 'Work path for package %s does not exist!'%(pkg)
                    break
            else:
                ret = 'Fail to create build command for package %s! Possibly there is no CMakeList, Makefile or GNUMakefile for the package.'%(pkg)
                break

            def setup_environment():
                os.chdir(work_path)
                setup_env(pkg_cfg[pkg]['env_var'])

            env_set = False
            cmd = []
            create_build_command(pkg, arch, variant, debug, verbose, 'cmake', nr_jobs,
                                 generator, cmd_type, config, pkg_cfg[pkg], cmd)
            if cmd:
                if config['os_type'] == 'windows':
                    env_set = True
                    setup_environment()
                    build_cmd_pipe = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.STDOUT)
                else:
                    build_cmd_pipe = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.STDOUT, preexec_fn = setup_environment)
                while True:
                    line = build_cmd_pipe.stdout.readline()
                    if not line: break
                    output(line)
                    log_fd.write(line)
                    if build_stop:
                        break
                if build_stop:
                    break
                build_cmd_pipe.wait()
                if build_cmd_pipe.returncode:
                    ret = 'cmake fail for %s! ret code: %d.'%(pkg, build_cmd_pipe.returncode)
                    break

            cmd = []
            create_build_command(pkg, arch, variant, debug, verbose, 'make', nr_jobs,
                                 generator, cmd_type, config, pkg_cfg[pkg], cmd)
            if cmd:
                if config['os_type'] == 'windows':
                    if not env_set:
                        env_set = True
                        setup_environment()
                    build_cmd_pipe = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.STDOUT)
                else:
                    build_cmd_pipe = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.STDOUT, preexec_fn = setup_environment)
                while True:
                    line = build_cmd_pipe.stdout.readline()
                    if not line: break
                    output(line)
                    log_fd.write(line)
                    if build_stop:
                        break
                if build_stop:
                    break
                build_cmd_pipe.wait()
                if build_cmd_pipe.returncode:
                    ret = 'make fail for %s!. ret code: %d.'%(pkg, build_cmd_pipe.returncode)
                    break
            if env_set:
                env_set = False
                unset_env(pkg_cfg[pkg]['env_var'])
    except BaseException as e:
        print(e)
        if not build_stop:
            ret = 'Fail running command!'
    if log_fd:
        log_fd.close()
    if build_stop:
        ret = 'break'
    build_stop = 0
    if env_set:
        env_set = False
        unset_env(pkg_cfg[cur_package]['env_var'])
    return {'info' : ret, 'package' : cur_package}

def guess_current_package(current_dir, config, arch):
    max_len = 0
    candidate_pkg = None
    candidate_base = None
    for pkg in config['PACKAGES'][arch]:
        pkg_base = config['PACKAGES'][arch][pkg]['Path']
        if current_dir.find(pkg_base) == 0:
            if len(pkg_base) > max_len:
                max_len = len(pkg_base)
                candidate_pkg = pkg
                candidate_base = pkg_base

    cur_pkg = []
    if candidate_pkg:
        for pkg in config['PACKAGES'][arch]:
            if candidate_base == config['PACKAGES'][arch][pkg]['Path']:
                cur_pkg.append(pkg)
    else:
        if current_dir.find(config['proj_root']) == 0:
            cur_pkg.append(build_all_target)

    return cur_pkg

def get_install_list(arch, package, config, variant):
    if not package in config['PACKAGES'][arch]:
        return {'info' : 'noexist'}

    config_package_path(config, arch, package, variant)
    manifest_file = os.path.join(config['PACKAGES'][arch][package]['BuildDir'], 'install_manifest.txt')
    try:
        fd = open(manifest_file, 'r')
    except IOError: 
        return {'info' : 'retry'}
    else:
        files = fd.read()
        fd.close()
        file_list = [i for i in files.split('\n') if i]
        file_list.sort()
        return {'info' : 'ok', 'files' : file_list}

def launch_dlt(config):
    dlt_viewer_path = config['proj_root'] + '/tools/dlt-viewer'
    cmd = 'LD_LIBRARY_PATH=' + dlt_viewer_path + ' ' + dlt_viewer_path + '/dlt_viewer > /dev/null 2>&1 &'
    os.system(cmd)
