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

def do_import_build_variant(config, build_cfg, variant, build_list, arch):
    if variant in build_list:
        return
    build_list[variant] = {'PACKAGES' : []}

    if not variant in build_cfg:
        config['ret'] = 'group %s is not defined!'%(variant)
        return

    if 'BASE' in build_cfg[variant]:
        for base_variant in build_cfg[variant]['BASE']:
            do_import_build_variant(config, build_cfg, base_variant, build_list, arch)
            if config['ret'] != 'ok':
                return
            build_list[variant]['PACKAGES'] += build_list[base_variant]['PACKAGES']

    if 'PACKAGES' in build_cfg[variant]:
        for pkg in build_cfg[variant]['PACKAGES']:
            if pkg in config['PACKAGES'][arch]:
                build_list[variant]['PACKAGES'].append(pkg)
            else:
                config['ret'] = 'variant %s: package %s does not exists!'%(variant, pkg)
                break

def import_build_variant(config, build_cfg, arch):
    build_list = {}
    for variant in config['VARIANT'][arch]:
        do_import_build_variant(config, build_cfg, variant, build_list, arch)

    return build_list

def init_private_config(config):
    config['private'] = {}
    for arch in config['TARGET_LIST']:
        config['private'][arch] = {'toolchain_root' : '',
                                   'c_compiler' : '',
                                   'cxx_compiler' : '',
                                   'asm_compiler' : '',
                                   'archiver' : '',
                                   'toolchain_file' : '',
                                   'sys_root' : '',
                                   'compiler_type' : '',
                                   'target_arch' : '',
                                   'target_os' : '',
                                   'cmake_generator' : '',
                                   'c_flags' : '',
                                   'cxx_flags' : '',
                                   'asm_flags' : '',
                                   'release_flags' : '',
                                   'debug_flags' : '',
                                   'macro_definition' : '',
                                   'shared_ld_flags' : '',
                                   'exe_ld_flags' : '',
                                   'lib_search_path' : '',
                                   'head_search_path' :'' 
                                   }

def import_configs(dst, src):
    for item in src:
        if item == 'TOOLCHAIN':
            dst['toolchain_root'] =  os.path.expanduser(src['TOOLCHAIN'])
        elif item == 'TOOLCHAIN_CC':
            dst['c_compiler'] = os.path.expanduser(src['TOOLCHAIN_CC'])
        elif item == 'TOOLCHAIN_CXX':
            dst['cxx_compiler'] = os.path.expanduser(src['TOOLCHAIN_CXX'])
        elif item == 'TOOLCHAIN_ASM':
            dst['asm_compiler'] = os.path.expanduser(src['TOOLCHAIN_ASM'])
        elif item == 'TOOLCHAIN_AR':
            dst['archiver'] = os.path.expanduser(src['TOOLCHAIN_AR'])
        elif item == 'SYSROOT':
            dst['sys_root'] =  os.path.expanduser(src['SYSROOT'])
        elif item == 'COMPILER_TYPE':
            dst['compiler_type'] = src['COMPILER_TYPE']
        elif item == 'TARGET_ARCH':
            dst['target_arch'] = src['TARGET_ARCH']
        elif item == 'TARGET_OS':
            dst['target_os'] = src['TARGET_OS']
        elif item == 'TOOLCHAIN_FILE':
            dst['toolchain_file'] = src['TOOLCHAIN_FILE']
        elif item == 'CMAKE_GENERATOR':
            generator = src['CMAKE_GENERATOR']
            if (generator in cmake_generator):
                dst['cmake_generator'] = generator 
            else:
                return {'ret' : 'error', 'info' : 'unknown generator %s!'%(generator)}
        elif item == 'C_FLAGS':
            if src['C_FLAGS']:
                dst['c_flags'] += ' ' + src['C_FLAGS']
        elif item == 'CXX_FLAGS':
            if src['CXX_FLAGS']:
                dst['cxx_flags'] += ' ' + src['CXX_FLAGS']
        elif item == 'ASM_FLAGS':
            if src['ASM_FLAGS']:
                dst['asm_flags'] += ' ' + src['ASM_FLAGS']
        elif item == 'REL_FLAGS':
            if src['REL_FLAGS']:
                dst['release_flags'] += ' ' + src['REL_FLAGS']
        elif item == 'DBG_FLAGS':
            if src['DBG_FLAGS']:
                dst['debug_flags'] += ' ' + src['DBG_FLAGS']
        elif item == 'MACRO_DEF':
            if (src['MACRO_DEF']):
                dst['macro_definition'] += ';' + ';'.join(src['MACRO_DEF'])
        elif item == 'SHA_LD_FLAGS':
            if src['SHA_LD_FLAGS']:
                dst['shared_ld_flags'] += ' ' + src['SHA_LD_FLAGS']
        elif item == 'EXE_LD_FLAGS':
            if src['EXE_LD_FLAGS']:
                dst['exe_ld_flags'] += ' ' + src['EXE_LD_FLAGS']
        elif item == 'OTHER_LIB_PATH':
            if src['OTHER_LIB_PATH']:
                dst['lib_search_path'] = ';'.join([os.path.expanduser(x) for x in src['OTHER_LIB_PATH']]) + ';' + dst['lib_search_path']
        elif item == 'OTHER_INC_PATH':
            if src['OTHER_INC_PATH']:
                dst['head_search_path'] = ';'.join([os.path.expanduser(x) for x in src['OTHER_INC_PATH']]) + ';' + dst['head_search_path']

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
        private_cfg = json.loads(template.substitute(PROOT = config['proj_root']))
    except ValueError as e:
        return {'ret' : 'error', 'info' : '%s: Config file %s is not in json format!'%(str(e), cfg_file)}

    for arch in private_cfg:
        if arch in config['TARGET_LIST'] or arch == config['os_type']:
            if arch == config['os_type']:
                cfg_arch = config['HOST']
            else:
                cfg_arch = arch

            ret = import_configs(config['private'][cfg_arch], private_cfg[arch])
            if ret['ret'] != 'ok':
                return ret

            if not config['private'][cfg_arch]['target_arch']:
                return {'ret' : 'error', 'info' : 'TARGET_ARCH is not defined for %s!'%(arch)}
            if not config['private'][cfg_arch]['target_os']:
                return {'ret' : 'error', 'info' : 'TARGET_OS is not defined for %s!'%(arch)}

    for arch in config['private']:
        for item in config['private'][arch]:
            config['private'][arch][item] = config['private'][arch][item].lstrip('; ')
            config['private'][arch][item] = config['private'][arch][item].rstrip('; ')

    return {'ret' : 'ok', 'info' : None}

def import_private_config(config):
    init_private_config(config)
    files = [
             # default config
             os.path.join(config['proj_root'], 'tools', 'buildCentral', 'rules', 'buildcentralrc'),
             # project specific config
             os.path.join(config['proj_root'], 'project', 'build', 'buildcentralrc'),
             # private config
             os.path.join('~', '.build_central')
            ]

    for cfg_file in files:
        ret = do_import_private_config(config, os.path.expanduser(cfg_file))
        if ret['ret'] != 'ok':
            return ret

    for arch in config['TARGET_LIST']:
        if not arch in config['private']:
            return {'ret' : 'error', 'info' : 'Arch %s is specified but not configured!'%(arch)}

    return {'ret' : 'ok', 'info' : None}

def config_package_path(config, arch, pkg, variant):
    src_path = os.path.abspath(os.path.join(config['proj_root'], config['PACKAGES'][arch][pkg]['Path']))
    output_dir = config.get('OUTPUT_DIR', src_path)
    if os.path.isfile(src_path):
        config['PACKAGES'][arch][pkg]['Path'] = os.path.join(output_dir,
                                                             config['PACKAGES'][arch][pkg]['Path'])
        config['PACKAGES'][arch][pkg]['PackageFile'] = src_path
    else:
        config['PACKAGES'][arch][pkg]['Path'] = src_path
        config['PACKAGES'][arch][pkg]['PackageFile'] = None 

    config['PACKAGES'][arch][pkg]['BuildDir'] = os.path.join(output_dir, 'build', variant, pkg, arch)
    if arch == config['HOST']:
        # no variant for host build
        config['PACKAGES'][arch][pkg]['StageDir'] = os.path.join(output_dir, 'stage', arch)
    else:
        config['PACKAGES'][arch][pkg]['StageDir'] = os.path.join(output_dir, 'stage', variant, arch)

def load_build_config(cfg_dir, proj_root):
    config = {'ret' : 'ok'}
    if not proj_root:
        proj_root = guess_project_root()
    config['proj_root'] = proj_root

    config['platform_info'] = platform.uname()
    os_name = config['platform_info'][0]
    if 'Windows' in os_name:
        config['os_type'] = 'windows'
    elif 'Linux' in os_name:
        config['os_type'] = 'linux'
    elif 'CYGWIN' in os_name:
        config['os_type'] = 'cygwin'
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
        """
        template = Template(fd.read())
        fd.close()
        try:
            cfg = json.loads(template.substitute(LD_LIBRARY_PATH = os.environ.get('LD_LIBRARY_PATH'),
                        PATH = os.environ.get('PATH'),
                        ROOT = proj_root))
        except ValueError as e:
            config['ret'] = '%s: Config file %s is not in json format!'%(str(e), cfg_file)
            return config
        """
        tmp = fd.read()
        fd.close()
        try:
            cfg = json.loads(tmp)
        except ValueError as e:
            config['ret'] = '%s: Config file %s is not in json format!'%(str(e), cfg_file)
            return config

        config['PROJECT_NAME'] = cfg.get('PROJECT_NAME', None)
        config['RUNTIME_ENV'] = cfg.get('RUNTIME_ENV', {})
        config['LOGO'] = cfg.get('LOGO', None)

        config['HOST'] = cfg.get('HOST', None)
        if 'TARGETS' in cfg:
            config['TARGET_LIST'] = cfg['TARGETS']
        else:
            config['ret'] = 'TARGETS should be defined!'
            return config
        if 'DEFAULT_TARGET' in cfg:
            config['DEFAULT_TARGET'] = cfg['DEFAULT_TARGET']
            if not config['DEFAULT_TARGET'] in config['TARGET_LIST']:
                config['ret'] = 'Invalid DEFAULT_TARGET!'
                return config
        else:
            config['ret'] = 'DEFAULT_TARGET should be defined!'
            return config
        if 'VARIANTS' in cfg:
            config['VARIANT_LIST'] = cfg['VARIANTS']
        else:
            config['ret'] = 'VARIANTS should be defined!'
            return config
        if 'DEFAULT_VARIANT' in cfg:
            config['DEFAULT_VARIANT'] = cfg['DEFAULT_VARIANT']
            if not config['DEFAULT_VARIANT'] in config['VARIANT_LIST']:
                config['ret'] = 'Invalid DEFAULT_VARIANT!'
                return config
        else:
            config['ret'] = 'DEFAULT_VARIANT should be defined!'
            return config

        ret = import_private_config(config)
        if ret['ret'] != 'ok':
            config['ret'] = ret['info']
            return config

        config['OUTPUT_DIR'] = os.path.join(proj_root, 'output')
        config['LOG_DIR'] = os.path.join(config['OUTPUT_DIR'], 'log')
        env_str = ''
        for env in config['RUNTIME_ENV']:
            env_str += 'export ' + env + '=' + config['RUNTIME_ENV'][env] + ';'
        config['RUNTIME_ENV_STR'] = env_str

        config['PACKAGES'] = {}
        if 'PACKAGES'in cfg:
            for arch in config['TARGET_LIST']:
                config['PACKAGES'][arch] = copy.deepcopy(cfg['PACKAGES'])
        else:
            for arch in config['TARGET_LIST']:
                config['PACKAGES'][arch] = {}

        if 'PACKAGES-PER-ARCH'in cfg:
            for arch in cfg['PACKAGES-PER-ARCH']:
                if not arch in config['TARGET_LIST']:
                    config['ret'] = 'Error! arch %s in PACKAGES-PER-ARCH tag is invalid!'%(arch)
                    return config
                for pkg in cfg['PACKAGES-PER-ARCH'][arch]:
                    if not pkg in config['PACKAGES'][arch]:
                        config['PACKAGES'][arch][pkg] = {}
                    for item in cfg['PACKAGES-PER-ARCH'][arch][pkg]:
                        config['PACKAGES'][arch][pkg][item] = cfg['PACKAGES-PER-ARCH'][arch][pkg][item]

        config['BUILD'] = {}
        config['VARIANT'] = {}
        if 'BUILD' in cfg:
            for arch in cfg['BUILD']:
                if not arch in config['TARGET_LIST']:
                    config['ret'] = 'Arch %s is invalid for BUILD in %s!'%(arch, cfg_file)
                    return config
                config['VARIANT'][arch] = []
                for group in cfg['BUILD'][arch]:
                    if group in config['VARIANT_LIST']:
                        config['VARIANT'][arch] += [group]
                if not config['DEFAULT_VARIANT'] in cfg['BUILD'][arch]:
                    config['ret'] = 'Default variant %s defined by DEFAULT_VARIANT is not in arch %s!'%(config['DEFAULT_VARIANT'], arch)
                    return config
                config['BUILD'][arch] = import_build_variant(config, cfg['BUILD'][arch], arch)
                if config['ret'] != 'ok':
                    config['ret'] = 'Error! Arch %s, '%(arch) + config['ret']
                    return config

                for build in config['VARIANT'][arch]:
                    config['BUILD'][arch][build]['GRAPH'] = nx.DiGraph()

                    for pkg in config['BUILD'][arch][build]['PACKAGES']:
                        if not pkg in config['PACKAGES'][arch]:
                            config['ret'] = 'Arch: %s, variant %s: Package %s is not defined in PACKAGE in file %s!'%(arch, build, pkg, cfg_file)
                            return config

                        if 'Dependency' in config['PACKAGES'][arch][pkg]:
                            for dep_pkg in config['PACKAGES'][arch][pkg]['Dependency']:
                                if not dep_pkg in config['PACKAGES'][arch]:
                                    config['ret'] = 'Arch: %s, variant %s, Package %s is not defined in Dependency in file %s!'%(arch, build, dep_pkg, cfg_file)
                                    return config
                                config['BUILD'][arch][build]['GRAPH'].add_edge(pkg, dep_pkg)

                    for pkg in config['BUILD'][arch][build]['GRAPH']:
                        if not pkg in config['BUILD'][arch][build]['PACKAGES']:
                            #print('File %s, arch %s, variant %s: package %s is depended but not list for build!'%(cfg_file, arch, build, pkg))
                            pass

                    loop_str = ''
                    for loop in nx.simple_cycles(config['BUILD'][arch][build]['GRAPH']):
                        loop_str += str(loop) + ', '

                    if loop_str:
                        config['ret'] = 'File %s, arch %s, variant %s: Loop dependency is found: %s!'%(cfg_file, arch, build, str(loop))
                        return config

                    root_pkg = []
                    for pkg, degree in config['BUILD'][arch][build]['GRAPH'].in_degree():
                        if degree == 0:
                            root_pkg.append(pkg)
                    for pkg in root_pkg:
                        config['BUILD'][arch][build]['GRAPH'].add_edge(build_all_target, pkg)

                    for pkg in config['BUILD'][arch][build]['PACKAGES']:
                        if not pkg in config['BUILD'][arch][build]['GRAPH']:
                            config['BUILD'][arch][build]['GRAPH'].add_edge(build_all_target, pkg)

    host_stage_dir = os.path.join(config['OUTPUT_DIR'], 'stage', config['HOST'])
    bins = (os.path.join(config['proj_root'], 'tools', 'bin', config['os_type']),
            os.path.join(host_stage_dir, 'bin'),
            os.path.join(host_stage_dir, 'usr/bin'))
    libs = (os.path.join(config['proj_root'], 'tools', 'lib', config['os_type']),
            os.path.join(host_stage_dir, 'lib'),
            os.path.join(host_stage_dir, 'usr/lib'))

    build_path = ''
    build_lib = ''
    for path in bins:
        if os.path.exists(path):
            if (build_path):
                build_path += os.pathsep + path
            else:
                build_path = path

    for lib in libs:
        if os.path.exists(lib):
            if (build_lib):
                build_lib += os.pathsep + lib 
            else:
                build_lib = lib 

    config['build_path'] = build_path 
    config['build_lib'] = build_lib 

    return config

def add_definition(cmd, var, value = None):
    if value is None:
        cmd += ['-D' + var]
    else:
        cmd += ['-D' + var + '=' + value]

def setup_global_build_env(arch, config):
    if config['build_path']:
        env = os.getenv('PATH')
        if env:
            env += os.pathsep + config['build_path']
        else:
            env = config['build_path']
        os.putenv('PATH', env)

    if config['build_lib']:
        env = os.getenv('LD_LIBRARY_PATH')
        if env:
            env += os.pathsep + config['build_lib'] 
        else:
            env = config['build_lib']
        os.putenv('LD_LIBRARY_PATH', env)

def setup_package_build_env(private_config, env, item):
    if private_config[item]:
        os.putenv(env, private_config[item])
    else:
        os.unsetenv(env)

def get_generator_id(generator, arch, config):
    if not generator:
        if arch in config['private']:
            if config['private'][arch]['cmake_generator']:
                generator = config['private'][arch]['cmake_generator']
    if not generator:
        generator = 'eunix'
        if config['os_type'] == 'windows':
            if arch == config['HOST'] or arch == 'rh850':
                generator = 'nmake'
    return generator

def check_generator(generator, arch, config):
    return cmake_generator[get_generator_id(generator, arch, config)]

def get_build_cmd_type(package, arch, config):
    type = 'unknown'
    package_base = config['PACKAGES'][arch][package]['Path']
    f = os.path.join(package_base, 'build_package')
    if os.access(f, os.X_OK):
        type = 'cmd'
    elif os.path.exists(os.path.join(package_base, 'CMakeLists.txt')): 
        type = 'cmake'
    elif os.path.exists(os.path.join(package_base, 'Makefile')) or os.path.exists(os.path.join(package_base, 'GNUMakefile')): 
        type = 'make'
    return type

def create_build_command(package, arch, variant, debug, verbose, stage, nr_jobs, generator, type, config, cmd):
    private_config = copy.deepcopy(config['private'][arch])
    import_configs(private_config, config['PACKAGES'][arch][package])

    if get_generator_id(generator, arch, config) == 'nmake':
        make_tool = ['nmake']
        make_tool_with_job = ['nmake']
    else:
        make_tool = ['make']
        make_tool_with_job = ['make', '-j', str(nr_jobs)]

    package_base = config['PACKAGES'][arch][package]['Path']
    if type == 'cmd':
        # if exists 'build_package' file, run it;
        f = os.path.join(package_base, 'build_package')
        if stage == 'clean':
            cmd += [f, '-c', config['VARIANT_LIST'][variant]['MACRO']]
        elif stage == 'make':
            cmd += [f, '-m', config['VARIANT_LIST'][variant]['MACRO']]
        elif stage == 'make_install':
            cmd += [f, '-i', config['VARIANT_LIST'][variant]['MACRO']]
        elif stage == 'uninstall':
            cmd += [f, '-u', config['VARIANT_LIST'][variant]['MACRO']]
    elif type == 'cmake':
        # if exists 'CMakeLists.txt', cmake it;
        setup_package_build_env(private_config, 'C_COMPILER', 'c_compiler')
        setup_package_build_env(private_config, 'CXX_COMPILER', 'cxx_compiler')
        if stage == 'clean':
            cmd += make_tool +  ['clean']
        elif stage == 'cmake':
            cmd += ['cmake']
            add_definition(cmd, 'PROJECT_ROOT', config['proj_root'])
            rule_dir = os.path.join(config['proj_root'], 'tools', 'buildCentral', 'rules')
            add_definition(cmd, 'RULE_DIR', rule_dir)
            if arch != config['HOST']:
                toolchain_file = private_config['toolchain_file']
                if not toolchain_file:
                    toolchain_file = 'toolchain.cmake'
                toolchain_file = os.path.join(rule_dir, toolchain_file)
                add_definition(cmd, 'CMAKE_TOOLCHAIN_FILE', toolchain_file)
            if debug:
                add_definition(cmd, 'CMAKE_BUILD_TYPE', 'Debug')
            else:
                add_definition(cmd, 'CMAKE_BUILD_TYPE', 'Release')

            generator = check_generator(generator, arch, config) 
            cmd.append('-G')
            cmd.append(generator)

            make_var = config['PACKAGES'][arch][package].get('MakeVar', [])
            if make_var:
                for d in make_var:
                    add_definition(cmd, d)

            macro_var = private_config['macro_definition']
            package_macro_var = config['PACKAGES'][arch][package].get('BuildVar', [])
            macro = None
            if macro_var:
                macro = macro_var
            if package_macro_var:
                macro += ';' + ';'.join(package_macro_var)
            if macro:
                add_definition(cmd, 'MACRO_DEF', macro)

            add_definition(cmd, 'MACRO_VARIANT', config['VARIANT_LIST'][variant]['MACRO'])

            if private_config['toolchain_root']:   add_definition(cmd, 'TOOL_ROOT',        private_config['toolchain_root'])
            if private_config['compiler_type']:    add_definition(cmd, 'COMPILER_TYPE',    private_config['compiler_type'])
            if private_config['target_arch']:      add_definition(cmd, 'TARGET_ARCH',      private_config['target_arch'])
            if private_config['target_os']:        add_definition(cmd, 'TARGET_OS',        private_config['target_os'])
            if private_config['c_flags']:          add_definition(cmd, 'CMAKE_C_FLAGS',    private_config['c_flags'])
            if private_config['archiver']:         add_definition(cmd, 'CMAKE_AR',         private_config['archiver'])
            if private_config['c_flags']:          add_definition(cmd, 'CMAKE_C_FLAGS',    private_config['c_flags'])
            if private_config['asm_compiler']:     add_definition(cmd, 'CMAKE_ASM_COMPILER', private_config['asm_compiler'])
            if private_config['asm_flags']:        add_definition(cmd, 'CMAKE_ASM_FLAGS',  private_config['asm_flags'])
            if private_config['cxx_flags']:        add_definition(cmd, 'CMAKE_CXX_FLAGS',  private_config['cxx_flags'])
            if private_config['release_flags']:    add_definition(cmd, 'REL_FLAGS',        private_config['release_flags'])
            if private_config['debug_flags']:      add_definition(cmd, 'DBG_FLAGS',        private_config['debug_flags'])
            if private_config['shared_ld_flags']:  add_definition(cmd, 'CMAKE_SHARED_LINKER_FLAGS', private_config['shared_ld_flags'])
            if private_config['exe_ld_flags']:     add_definition(cmd, 'CMAKE_EXE_LINKER_FLAGS', private_config['exe_ld_flags'])
            if private_config['lib_search_path']:  add_definition(cmd, 'LIB_PATH',         private_config['lib_search_path'])
            if private_config['head_search_path']: add_definition(cmd, 'INC_PATH',         private_config['head_search_path'])

            if verbose:
                add_definition(cmd, 'CMAKE_VERBOSE_MAKEFILE', 'on')
            else:
                add_definition(cmd, 'CMAKE_VERBOSE_MAKEFILE', 'off')

            sys_root = os.getenv('SROOT_OVERRIDE')
            if not sys_root:
                sys_root = private_config['sys_root']
            stage_root = config['PACKAGES'][arch][package]['StageDir']
            if stage_root:
                if sys_root:
                    sys_root = stage_root
                else:
                    sys_root += ';' + stage_root
                add_definition(cmd, 'CMAKE_INSTALL_PREFIX', stage_root)
            if sys_root:
                add_definition(cmd, 'SYSTEM_ROOT', sys_root)

            add_definition(cmd, 'PROJECT_ROOT', config['proj_root'])

            definitions = config.get('additional_cmake_definition')
            if definitions:
                for item in definitions:
                    cmd += ['-D' + item]

            add_definition(cmd, 'PACKAGE_NAME', package)
            cmd.append(package_base)
        elif stage == 'make':
            cmd += make_tool_with_job
        elif stage == 'make_install':
            generator = check_generator(generator, arch, config) 
            if 'Visual Studio' in generator:
                cmd = []
            else:
                cmd += make_tool_with_job + ['install']
        elif stage == 'uninstall':
            cmd += make_tool + ['uninstall']
    elif type == 'make':
        setup_package_build_env(private_config, 'CC', 'c_compiler')
        setup_package_build_env(private_config, 'CXX', 'cxx_compiler')
        setup_package_build_env(private_config, 'CFLAGS', 'c_flags')
        setup_package_build_env(private_config, 'CPPFLAGS', 'cxx_flags')

        # if exists 'Makefile' or 'GNUMakefile', make it;
        if stage == 'clean':
            cmd += make_tool + ['clean']
        elif stage == 'make':
            cmd += make_tool_with_job
        elif stage == 'make_install':
            cmd += make_tool_with_job + ['install']
        elif stage == 'uninstall':
            cmd += make_tool + ['uninstall']
        else:
            return[]

        stage_root = config['PACKAGES'][arch][package]['StageDir']
        make_var = config['PACKAGES'][arch][package].get('MakeVar', [])
        variables = ''
        if make_var:
            variables = ' '.join(make_var)

        if variables:
            cmd += [' ' + variables]
        if stage_root:
            cmd += [' DESTDIR=' + stage_root]

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

def generate_build_order(G, package, build_list):
    if not package in build_list:
        build_list.append(package)
        figure_out_build_order(G, package, build_list)

def should_install(config, arch, package):
    return config['PACKAGES'][arch][package].get('Install', True)

def do_build_packages(packages, arch, variant, debug, verbose, clean, not_build, nr_jobs, generator, config, output):
    global build_stop
    global build_cmd_pipe
    cur_package = '' 
    build_stop = 0
    current_dir = os.getcwd()
    ret = 'ok'
    log_base = os.path.join(config['LOG_DIR'], arch)
    if not os.path.exists(log_base):
        try:
            os.makedirs(log_base)
        except:
            return {'info' : 'Unable to create log dir %s'%(log_base), 'package' : None}
    log_fd = open(os.path.join(log_base, 'log'), 'w')
    if build_all_target in packages:
        del(packages[packages.index(build_all_target)])

    if nr_jobs < 1:
        nr_jobs = 1

    # ==== Clean packages ====
    if clean:
        for pkg in packages:
            config_package_path(config, arch, pkg, variant)
            cur_package = pkg
            type = get_build_cmd_type(pkg, arch, config)
            if type == 'cmake':
                work_path = config['PACKAGES'][arch][pkg]['BuildDir']
            else:
                work_path = config['PACKAGES'][arch][pkg]['Path']
            if os.path.exists(work_path):
                try:
                    os.chdir(work_path)

                    if clean == 'uninstall_clean' and should_install(config, arch, pkg):
                        cmd = []
                        create_build_command(pkg, arch, variant, debug, verbose, 'uninstall', nr_jobs, generator, type, config, cmd)
                        if cmd:
                            build_cmd_pipe = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.STDOUT)
                            while True:
                                line = build_cmd_pipe.stdout.readline()
                                if not line: break
                                output(line)
                                log_fd.write(line)
                                if build_stop:
                                    break
                            if build_stop:
                                break

                    if clean == 'uninstall_clean' or clean == 'clean_only':
                        cmd = []
                        create_build_command(pkg, arch, variant, debug, verbose, 'clean', nr_jobs, generator, type, config, cmd)
                        if cmd:
                            build_cmd_pipe = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.STDOUT)
                            while True:
                                line = build_cmd_pipe.stdout.readline()
                                if not line: break
                                output(line)
                                log_fd.write(line)
                                if build_stop:
                                    break

                except:
                    pass
                try:
                    if type == 'cmake':
                        print('Removing working directory: ' + work_path)
                        shutil.rmtree(work_path, ignore_errors=True)
                except:
                    pass

                if build_stop:
                    break

    if not_build:
        os.chdir(current_dir)
        return {'info' : ret, 'package' : None}

        # ==== Build packages ====
    setup_global_build_env(arch, config)
    package_built = {}
    try:
        for pkg in packages:
            config_package_path(config, arch, pkg, variant)
            cur_package = pkg
            package_base = config['PACKAGES'][arch][pkg]['Path']
            if config['PACKAGES'][arch][pkg]['PackageFile']:
                extract_dir = config['PACKAGES'][arch][pkg]['Path']
                # in this case package_base equal to extract_dir
                try:
                    tar = tarfile.open(config['PACKAGES'][arch][pkg]['PackageFile'])
                except:
                    os.chdir(current_dir)
                    return {'info' : 'Package %s: Package file %s does not exist or is not valid tar ball!'%(cur_package, config['PACKAGES'][arch][pkg]['PackageFile']), 'package' : cur_package}
                else:
                    tar.extractall(path=os.path.dirname(extract_dir))
                    tar.close()
                if not os.path.exists(extract_dir):
                    os.chdir(current_dir)
                    return {'info' : 'Package %s: Package file %s is not extracted to %s!'%(cur_package, config['PACKAGES'][arch][pkg]['PackageFile'], extract_dir), 'package' : cur_package}

            if not os.path.exists(package_base):
                os.chdir(current_dir)
                return {'info' : 'Package %s: base directory %s does not exist!'%(cur_package, package_base), 'package' : cur_package}

            type = get_build_cmd_type(pkg, arch, config)
            if type == 'cmake':
                work_path = config['PACKAGES'][arch][pkg]['BuildDir']
            elif type == 'unknown':
                ret = 'Fail to create build command for package %s! Possibly there is no CMakeList, Makefile or GNUMakefile for the package.'%(pkg)
                break
            else:
                work_path = package_base

            if work_path in package_built:
                package_cleared = package_built[work_path]
                try:
                    print('==== Note: package %s is cleared because work path of %s overlap with it.'%(package_cleared, pkg))
                    do_build_packages([package_cleared], arch, variant, debug, verbose, 'clean_only', True, nr_jobs, generator, config, output)
                except Exception as e:
                    pass
            else:
                package_built[work_path] = pkg

            if not os.path.exists(work_path):
                try:
                    os.makedirs(work_path)
                except:
                    os.chdir(current_dir)
                    return {'info' : 'Package %s: cannot create work path %s!'%s(cur_package, work_path)}

            os.chdir(work_path)
            cmd = []
            create_build_command(pkg, arch, variant, debug, verbose, 'cmake', nr_jobs, generator, type, config, cmd)
            if cmd:
                build_cmd_pipe = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.STDOUT)
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
            make_type = 'make'
            if should_install(config, arch, pkg):
                make_type = 'make_install'
            create_build_command(pkg, arch, variant, debug, verbose, make_type, nr_jobs, generator, type, config, cmd)
            if cmd:
                build_cmd_pipe = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.STDOUT)
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
    except:
        if not build_stop:
            ret = 'Fail running command!'
    if log_fd:
        log_fd.close()
    if build_stop:
        ret = 'break'
    build_stop = 0
    os.chdir(current_dir)
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
