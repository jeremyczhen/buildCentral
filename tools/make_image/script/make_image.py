#!/usr/bin/python
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

import os
from stat import *
import shutil
from string import Template
import re
import simplejson as json
import glob
import argparse
import magic

def do_print(line):
    print line,

#class cfgError(Exception):
#    def __init__(self, reason):
#        Exception.__init__(self, reason)

def guess_project_root():
    signature = set(["deliveries", "workspace", "sys_root", "toolchain"])
    cwd = cur_dir = os.getcwd()
    parent_dir = os.path.abspath(os.path.join(cur_dir, os.pardir))
    while (parent_dir != cur_dir):
        if signature.issubset(set(os.listdir(cur_dir))):
            break
        cur_dir = parent_dir
        parent_dir = os.path.abspath(os.path.join(cur_dir, os.pardir))
    if os.path.dirname(os.path.realpath(cur_dir)) == cur_dir:
        output_method('Cannot fild project root! using curent directory instead.\n')
        cur_dir = cwd
    return cur_dir

def import_private_config(config):
    priv_cfg_file = '~/.build_central'
    try:
        fd = open(os.path.expanduser(priv_cfg_file))
    except IOError:
        return {'ret' : 'ok', 'info' : 'Warning: %s does not exists and cross-compiling is not supported!'%(priv_cfg_file)}
    try:
        private_cfg = json.loads(fd.read())
    except ValueError as e:
        fd.close()
        return {'ret' : 'error', 'info' : '%s: Config file %s is not in json format!'%(str(e), priv_cfg_file)}
    fd.close()

    key_map = {'TOOLCHAIN' : 'toolchain_root',
               'SYSROOT' : 'sys_root',
               'TOOLCHAIN_PREFIX' : 'toolchain_prefix',
               'ROOTFS' : 'root_fs'}
    for key in key_map:
        config[key_map[key]] = {}
        for arch in config['archs']:
            config[key_map[key]][arch] = ''

        if key in private_cfg:
            for arch in private_cfg[key]:
                if arch in config['archs']:
                    config[key_map[key]][arch] = os.path.expanduser(private_cfg[key][arch])

    return {'ret' : 'ok', 'info' : None}

def strip_file(file_name):
    try:
        file_type = magic.from_file(file_name)
    except:
        return
    if file_type[:3] == 'ELF':
        cmd = '%s %s'%(platform_strip_cmd, file_name)
        output_method('Stripping: %s...\n'%(cmd))
        os.system(cmd)

def copy_one_file(src_file, dst_file, no_run, symlinks, user, src_mode, dst_mode, acc_mode, strip):
    try:
        if symlinks and S_ISLNK(src_mode):
            if not dst_mode is None and S_ISDIR(dst_mode):
                dst_file = os.path.join(dst_file, os.path.basename(src_file))
            output_method('%s -> %s: creating symbol link...\n'%(src_file, dst_file))
            if not no_run:
                linkto = os.readlink(src_file)
                os.symlink(linkto, dst_file)
        else:
            output_method('%s -> %s: coping file...\n'%(src_file, dst_file))
            if not no_run:
                shutil.copy2(src_file, dst_file)
            if strip and platform_strip_cmd:
                strip_file(dst_file)

    except (IOError, OSError) as e:
        output_method("Error: %s while copy from %s to %s!\n"%(str(e), src_file, dst_file))
        return -1
    return 0

global_ignore_list = ['.svn', '.git']
def do_copy_tree(src, src_root, dst_root, rn_map, installed_list, no_run, ignore_list, symlinks, user, acc_mode, strip):
    if src in ignore_list or os.path.basename(src) in global_ignore_list:
        output_method('%s is ignored.\n'%(src))
        return 0
    
    try:
        src_mode = os.lstat(src).st_mode
    except:
        output_method('Error: file %s does not exist!\n'%s(src))
        return -1 
    dst = src.replace(src_root, dst_root)
    if S_ISDIR(src_mode):
        if no_run:
            if dst in installed_list['file']:
                output_method('Error: file %s exists but directory is expected while processing %s.\n'%(dst, src))
                return -1
            elif not dst in installed_list['folder']:
                output_method('%s: creating directory...\n'%(dst))
        else:
            try:
                dst_mode = os.lstat(dst).st_mode
            except:
                output_method('%s: creating directory...\n'%(dst))
                os.makedirs(dst)
            else:
                if not S_ISDIR(dst_mode):
                    output_method('Error: file %s exists but directory is expected while processing %s.\n'%(dst, src))
                    return -1

        installed_list['folder'][dst] = True 
        for f in os.listdir(src):
            sub_src = os.path.join(src, f)
            ret = do_copy_tree(sub_src, src_root, dst_root, rn_map, installed_list, no_run, ignore_list, symlinks, user, acc_mode, strip)
            if ret:
                return ret
    else:
        dst_mode = None
        if no_run:
            if dst in installed_list['folder'] or dst in installed_list['file']:
                output_method("Error: file %s exists while coping %s!\n"%(dst, src))
                return -1
        else:
            try:
                dst_mode = os.lstat(dst).st_mode
            except:
                dir_name = os.path.dirname(dst)
                try:
                    os.lstat(dir_name)
                except:
                    os.makedirs(dir_name)
            else:
                output_method("Error: file %s exists while coping %s!\n"%(dst, src))
                return -1

        if dst in rn_map:
            output_method('%s -> %s: renaming...\n'%(dst, rn_map[dst]))
            dst = rn_map[dst]
        installed_list['file'][dst] = src
        ret = copy_one_file(src, dst, no_run, symlinks, user, src_mode, dst_mode, acc_mode, strip)
        if ret:
            return ret

def smart_copy(src, dst, orig_rn_map = {}, installed_list = {}, no_run = False, ignore_list = [], symlinks=True, user=None, acc_mode=None, strip = False):
    abs_src = os.path.abspath(src)
    abs_dst = os.path.abspath(dst)
    src_root = abs_src
    dst_root = abs_dst
    try:
        src_mode = os.lstat(abs_src).st_mode
    except:
        pass
    else:
        if S_ISDIR(src_mode):
            if src[-1] != '/':
                dst_root = os.path.join(dst_root, os.path.basename(abs_src))
        else:
            src_root = os.path.dirname(abs_src)

    rn_map = {}
    for item in orig_rn_map:
        rn_dir = os.path.dirname(item)
        rn_from = os.path.join(dst_root, item)
        rn_to = os.path.join(dst_root, rn_dir, orig_rn_map[item])
        rn_map[os.path.abspath(rn_from)] = os.path.abspath(rn_to)

    ret = do_copy_tree(abs_src, src_root, dst_root, rn_map, installed_list, no_run, ignore_list, symlinks, user, acc_mode, strip)
    return ret

class file_manager:
    file_container = {}
    @classmethod
    def get_config_file(cls, file_name):
        abs_path = os.path.abspath(file_name)
        try:
            fc = cls.file_container[abs_path]
        except:
            return None
        return fc
    @classmethod
    def add_config_file(cls, cfg_name, cfg_file):
        cfg_name = os.path.abspath(cfg_name)
        if cfg_name in cls.file_container:
            return -1
        cls.file_container[cfg_name] = cfg_file
    @classmethod
    def print_map(cls):
        output_method(cls.file_container)


class config_file:
    def __init__(self, name):
        self.name = name
        self.tp = 'FILE'
        self.image_root = None
        self.package_container = {}
        self.group_container = {}
        self.installed = {'file' : {}, 'folder' : {}}
        try:
            fd = open(os.path.expanduser(self.name))
        except IOError as e:
            output_method(str(e) + '\n')
            raise Exception('Error: cannot open %s!'%(self.name))
        template = Template(fd.read())
        fd.close()

        try:
            self.config = json.loads(template.substitute(
                            ARCH = args.target_arch,
                            PROOT = project_root,
                            SROOT = mkimg_config['sys_root'][args.target_arch],
                            ROOTFS = mkimg_config['root_fs'][args.target_arch]
                        )
                  )
        except ValueError as e:
            output_method(str(e) + '\n')
            raise Exception('Config file %s is not in json format!'%(self.name))

        key = "IMAGE_ROOT"
        if key in self.config:
            self.image_root = self.config[key]

        file_manager.add_config_file(self.name, self)

    def check_and_deglob(self):
        for grp in self.group_container:
            if self.group_container[grp].check_and_deglob():
                return -1
        for pkg in self.package_container:
            if self.package_container[pkg].check_and_deglob():
                return -1
        return 0

    def install(self, groups = None, packages = None, no_run = False):
        for grp in self.group_container:
            if not groups is None and not grp in groups:
                continue
            if self.group_container[grp].install(self.image_root, '', '', self.installed, no_run, None):
                return -1
        for pkg in self.package_container:
            if not packages is None and not pkg in packages:
                continue
            if self.package_container[pkg].install(self.image_root, '', '', self.installed, no_run, None):
                return -1
        return 0

    def __str__(self):
        s = 'file: ' + self.name + '\n'
        for grp in self.group_container:
            s += '    group: ' + grp + '\n' + str(self.group_container[grp]) + '\n'
        for pkg in self.package_container:
            s += '    package: ' + pkg + '\n' + str(self.package_container[pkg]) + '\n'
        return s
    def __repr__(self):
        return self.__str__()

    def get_package(self, package_name):
        try:
            pkg = self.package_container[package_name]
        except:
            return None
        return pkg

    def get_group(self, group_name):
        try:
            grp = self.group_container[group_name]
        except:
            return None
        return grp

    def import_elements(self, groups = None, packages = None):
        key = 'MAP'
        if key in self.config:
            for package in self.config[key]:
                if not packages is None and not package in packages:
                    continue
                try:
                    pkg_map = package_map(package, self, self.config[key][package])
                except Exception as e:
                    return str(e)
                self.package_container[package] = pkg_map

        key = 'GROUP'
        if key in self.config:
            for group in self.config[key]:
                if not groups is None and not group in groups:
                    continue
                try:
                    grp = package_group(group, self, self.config[key][group])
                except Exception as e:
                    return str(e)
                self.group_container[group] = grp

        return None

def parse_group_rule(item):
    full_pattern = re.compile('(^[^:@]+):([^:@]+)@(.+)$')
    m = full_pattern.match(item)
    if m:
        tp = m.group(1)
        type_name = m.group(2)
        cfg_name = m.group(3)
    else:
        short_pattern = re.compile('(^[^:@]+):([^:@]+)$')
        m = short_pattern.match(item)
        if m:
            tp = m.group(1)
            type_name = m.group(2)
            cfg_name = None
        else:
            tp, type_name, cfg_name = None, None, None

    return tp, type_name, cfg_name

class package_group:
    def __init__(self, name, cfg_file, config):
        self.name = name
        self.tp = 'GROUP'
        self.owner = cfg_file
        self.sub_group = []

        ret = self.parse_config(config)
        if ret:
            raise Exception(ret)

    def check_and_deglob(self):
        for container in self.sub_group:
            for grp in container['group_container']:
                if container['group_container'][grp].check_and_deglob():
                    return -1
            for pkg in container['package_container']:
                if container['package_container'][pkg].check_and_deglob():
                    return -1

        return 0

    def install(self, image_root, path_offset, tracking_info, installed_list, no_run, strip):
        tracking_info += '-> GROUP:%s@%s'%(self.name, self.owner.name)
        for container in self.sub_group:
            do_strip = strip
            if do_strip is None:
                do_strip = container['strip']
            offset = os.path.join(path_offset, container['offset'])
            for grp in container['group_container']:
                if container['group_container'][grp].install(image_root, offset, tracking_info, installed_list, no_run, do_strip):
                    return -1
            for pkg in container['package_container']:
                if container['package_container'][pkg].install(image_root, offset, tracking_info, installed_list, no_run, do_strip):
                    return -1

        return 0

    def parse_config(self, config):
        for sub_grp in config:
            container = {'group_container' : {}, 'package_container' : {}, 'offset' : '', 'strip' : None}
            key = 'strip'
            if key in sub_grp:
                container[key] = sub_grp[key]
            key = 'offset'
            if key in sub_grp:
                if sub_grp[key]:
                    if sub_grp[key][0] == '/':
                        return 'Error: offset should be relative path for group %s in file %s!\n'%(self.name, self.owner.name)
                    container[key] = sub_grp[key]
            key = 'include'
            if key in sub_grp:
                for item in sub_grp[key]:
                    (tp, type_name, cfg_name) = parse_group_rule(item)
                    if not tp:
                        return 'Error: bad format for %s in file %s!'%(item, self.owner.name)

                    if not cfg_name:
                        cfg_name = self.owner.name
                    if tp == 'GROUP' or tp == 'MAP':
                        if tp == 'GROUP' and type_name == self.name and cfg_name == self.owner.name:
                            return 'Error: loop contain is found at %s in file %s!'%(item, self.owner.name)

                        cfg_name = os.path.abspath(cfg_name)
                        unique_key = tp + ':' + type_name + '@' + cfg_name
                        cfg_file = file_manager.get_config_file(cfg_name)
                        if not cfg_file:
                            try:
                                cfg_file = config_file(cfg_name)
                            except Exception as e:
                                output_method(str(e) + '\n')
                                cfg_file = None
                        if not cfg_file:
                            return 'Error: cannot import configure file at %s in file %s!'%(item, self.owner.name)

                        if tp == 'GROUP':
                            grp = cfg_file.get_group(type_name)
                            if not grp:
                                ret = cfg_file.import_elements([type_name], [])
                                if ret:
                                    return ret
                                grp = cfg_file.get_group(type_name)
                                if not grp:
                                    return 'Error: group %s is not found at %s in file %s!'%(type_name, item, self.owner.name)
                            container['group_container'][unique_key] = grp
                        else:
                            pkg = cfg_file.get_package(type_name)
                            if not pkg:
                                ret = cfg_file.import_elements([], [type_name])
                                if ret:
                                    return ret
                                pkg = cfg_file.get_package(type_name)
                                if not pkg:
                                    return 'Error: package %s is not found at %s in file %s!'%(type_name, item, self.owner.name)
                            container['package_container'][unique_key] = pkg
                    else:
                        return 'Error: type %s at %s in file %s is invalid!'%(tp, item, self.owner.name)
            self.sub_group.append(container)

        return None
    def __str__(self):
        s = ''
        for container in self.sub_group:
            for grp in container['group_container']:
                s += '       >group ' + container['group_container'][grp].name + '\n' + str(container['group_container'][grp]) + '       >endgroup ' + container['group_container'][grp].name + '\n'
            for pkg in container['package_container']:
                s += '       >package ' + container['package_container'][pkg].name + '\n' + str(container['package_container'][pkg]) + '       >endpackage ' + container['package_container'][pkg].name + '\n'
        return s
    def __repr__(self):
        return self.__str__()

class package_map:
    def __init__(self, name, cfg_file, config):
        self.name = name
        self.tp = 'MAP'
        self.owner = cfg_file 
        self.source = {}
        self.de_glob_map = {}

        ret = self.parse_config(config)
        if ret:
            raise Exception(ret)

    def parse_config(self, config):
        for dst_path in config:
            self.source[dst_path] = config[dst_path]
        return None

    def check_and_deglob(self):
        if self.de_glob_map:
            return 0
        for dst_path in self.source:
            self.de_glob_map[dst_path] = []
            for src in self.source[dst_path]:
                item_first = ['ignore', 'include']
                the_map = {}
                for item in item_first:
                    the_map[item] = []
                    if item in src:
                        for path in src[item]:
                            glob_list = glob.glob(path)
                            if glob_list:
                                for i in glob_list:
                                    d = os.path.abspath(i)
                                    if i[-1] == '/':
                                        d += '/'
                                    if item == 'include' and d in the_map['ignore']:
                                        continue
                                    if d in the_map[item]:
                                        output_method('Error: %s in %s already exists in MAP:%s@%s!\n'%(d, path, self.name, self.owner.name))
                                        return -1
                                    the_map[item].append(d)
                            elif item == 'include':
                                output_method('Error: source file %s does not exist in MAP:%s@%s!\n'%(path, self.name, self.owner.name))
                                return -1

                for item in src:
                    if item in item_first:
                        continue
                    if item == 'rename':
                        the_map[item] = {}
                        for rn_map in src[item]:
                            if '/' in src[item][rn_map]:
                                output_method('Error: destination of rename map should not contain / in MAP:%s@%s!\n'%(self.name, self.owner.name))
                                return -1
                            if rn_map[0] == '/':
                                the_map[item][rn_map[1:]] = src[item][rn_map]
                            else:
                                the_map[item][rn_map] = src[item][rn_map]
                    else:
                        the_map[item] = src[item]

            self.de_glob_map[dst_path].append(the_map)
        return 0

    def install(self, image_root, path_offset, tracking_info, installed_list, no_run, strip):
        tracking_info += '-> MAP:%s@%s'%(self.name, self.owner.name)
        output_method(tracking_info + '\n')

        for dst_path in self.de_glob_map:
            if dst_path[0] == '/':
                full_dst_path = os.path.join(image_root, path_offset, dst_path[1:])
            else:
                full_dst_path = os.path.join(image_root, path_offset, dst_path)

            for src in self.de_glob_map[dst_path]:
                if 'mode' in src:
                    mode = src['mode']
                else:
                    mode = None
                if 'usr' in src:
                    user = src['usr']
                else:
                    user = None
                do_strip = strip
                if do_strip is None:
                    if 'strip' in src:
                        do_strip = src['strip']

                for path in src['include']:
                    if 'rename' in src:
                        rename_list = src['rename']
                    else:
                        rename_list = {}
                    if 'ignore' in src:
                        ignore_list = src['ignore']
                    else:
                        ignore_list = []
                    if smart_copy(path, full_dst_path, rename_list, installed_list, no_run, ignore_list, True, user, mode, do_strip):
                        output_method('\n')
                        return -1

    def __str__(self):
        s = ''
        for dst_path in self.source:
            s += '       >' + dst_path + '\n'
            for src in self.source[dst_path]:
                for path in src['include']:
                    s += '        ' + path + '\n'
        return s
    def __repr__(self):
        return self.__str__()

parser = argparse.ArgumentParser()
parser.add_argument('-n', '--no_run', help='do not run but verify the config file', action='store_true')
parser.add_argument('-t', '--target_arch', help='specify target arch. Valid arch include x86_ubuntu, j6 and imx6', default='x86_ubuntu')
parser.add_argument('image_root', help='specify root of output image; will override IMAGE_ROOT in config file')
parser.add_argument('packages', help='specify the packages to build; separated by ","; format: [MAP|GROUP:package_name@]config_file')

args = parser.parse_args()

output_method = do_print
project_root = guess_project_root()
mkimg_config = {'archs' : ['x86_ubuntu', 'j6', 'imx6']}
ret = import_private_config(mkimg_config)
if ret['ret'] != 'ok':
    output_method(ret['info'] + '\n')
    exit(-1)
elif ret['info']:
    output_method(ret['info'] + '\n')

try:
    if args.target_arch == 'x86_ubuntu':
        platform_strip_cmd = '/usr/bin/strip'
    else:
        platform_strip_cmd = '%s/bin/%s-strip'%(mkimg_config['toolchain_root'][args.target_arch], 
                                   mkimg_config['toolchain_prefix'][args.target_arch])
    os.stat(platform_strip_cmd)
except:
    output_method('Warning: strip command is not found for platform %s!\n'%(args.target_arch))
    platform_strip_cmd = None

if not args.target_arch in mkimg_config['archs']:
    output_method('Error: invalid target architecture for %s!'%(args.target_arch))

cfg_file_list = {}
if args.packages:
    input_package_list = args.packages.split(',')
    for package in input_package_list:
        tp, type_name, cfg_name = parse_group_rule(package)
        if not cfg_name:
            output_method("Error: bad format: file name is not given in %s!\n"%(package))
            exit(-1)
        if not cfg_name in cfg_file_list:
            cfg_file_list[cfg_name] = {'package_list' : [], 'group_list' : []}
        if tp == 'MAP':
            if not cfg_file_list[cfg_name]['package_list'] is None:
                if type_name == '*':
                    cfg_file_list[cfg_name]['package_list'] = None
                else:
                    cfg_file_list[cfg_name]['package_list'].append(type_name)
        elif tp == 'GROUP':
            if not cfg_file_list[cfg_name]['group_list'] is None:
                if type_name == '*':
                    cfg_file_list[cfg_name]['group_list'] = None
                else:
                    cfg_file_list[cfg_name]['group_list'].append(type_name)
        elif not tp is None:
            output_method("Error: type %s for %s is invalid!\n"%(tp, package))
            exit(-1)

for cfg_name in cfg_file_list:
    cfg_file_list[cfg_name]['cfg_file'] = file_manager.get_config_file(cfg_name)
    if not cfg_file_list[cfg_name]['cfg_file']:
        try:
            cfg_file_list[cfg_name]['cfg_file'] = config_file(cfg_name)
        except Exception as e:
            output_method(str(e) + '\n')
            exit(-1)

    if args.image_root is None:
        if cfg_file_list[cfg_name]['cfg_file'].image_root is None:
            output_method("Error: please specify image root by either -r or IMAGE_ROOT in file %s!\n"%(cfg_name))
            exit(-1)
    else:
        cfg_file_list[cfg_name]['cfg_file'].image_root = args.image_root

    if cfg_file_list[cfg_name]['package_list']:
        for pkg in cfg_file_list[cfg_name]['package_list']:
            if not pkg in cfg_file_list[cfg_name]['cfg_file'].config['MAP']:
                output_method("Error: package %s is not defined in file %s!\n"%(pkg, cfg_name))

    if cfg_file_list[cfg_name]['group_list']:
        for grp in cfg_file_list[cfg_name]['group_list']:
            if not grp in cfg_file_list[cfg_name]['cfg_file'].config['GROUP']:
                output_method("Error: group %s is not defined in file %s!\n"%(grp, cfg_name))

    ret = cfg_file_list[cfg_name]['cfg_file'].import_elements(cfg_file_list[cfg_name]['group_list'], cfg_file_list[cfg_name]['package_list'])
    if (ret):
        output_method(ret)
        exit(-1)

    if cfg_file_list[cfg_name]['cfg_file'].check_and_deglob():
        exit(-1)

for cfg_name in cfg_file_list:
    if cfg_file_list[cfg_name]['cfg_file'].install(cfg_file_list[cfg_name]['group_list'], cfg_file_list[cfg_name]['package_list'], args.no_run):
        exit(-1)

exit(0)
