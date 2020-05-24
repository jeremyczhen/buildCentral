#!/usr/bin/python
# encoding: utf-8
 
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

from Tkinter import *
import json
import os
from tkMessageBox import *
from ttk import *
import bc_core as bcc
import argparse
import networkx as nx
import matplotlib.pyplot as plt

root = Tk()
root.resizable(0,0)

tk_service_list = None
tk_service_build_list = None
tk_build_button = None
tk_message_box = None
variant_zone = None
window_width =840
window_height = 610
message_window_height = 8

def draw_packages(config, arch, variant):
    graphs = config['BUILD'][arch][variant]['GRAPH']
    nx.draw_networkx(graphs,
                     pos=nx.circular_layout(graphs),
                     width=2,
                     font_size=8,
                     edge_color='black')
    #picture_name = os.path.join(config['proj_root'], 'tools', 'buildCentral', '.packages.png')
    #plt.savefig(picture_name)
    #return picture_name
    plt.show()

def build_packages(packages, config, output, clean = False, not_build = False):
    global tk_build_button 
    arch = globalConfig.get_arch()
    debug = globalConfig.Debug.get()
    verbose = globalConfig.Verbose.get()
    variant = globalConfig.get_variant()
    nr_jobs = globalConfig.Jobs.get()
    clean_type = None
    if clean:
        clean_type = 'uninstall_clean'
    ret = bcc.do_build_packages(packages,
                                arch,
                                variant,
                                debug,
                                verbose,
                                clean_type,
                                not_build,
                                nr_jobs,
                                None,
                                config,
                                output)
    if ret['info'] == 'ok':
        showinfo('Result', 'Success!')
    elif ret['info'] != 'break':
        showerror('Fail!', ret['info'])

    tk_build_button.build_bt.config(text='Build')
    tk_build_button.clean_bt.config(text='Clean')
    bcc.build_cmd_pipe = None

def createLabelEntry(_parent, _name, _text_side, _pack_opt={'fill':X}, _entry_opt={}):
    frame = Frame(_parent)
    frame.pack(**_pack_opt)
    Label(frame, text=_name).pack(side=_text_side)
    Entry(frame, **_entry_opt).pack(side=RIGHT)

def Scrolled(_class, _parent, _mode='e', _label_opt={}, _pack_opt={}, _widget_opt={}):
    if _label_opt:
        frame = LabelFrame(_parent, **_label_opt)
    else:
        frame = Frame(_parent)

    frame.pack(**_pack_opt)

    v_bar = None
    h_bar = None
    if 'e' in _mode:
        v_bar = Scrollbar(frame)
        v_bar.pack(side=RIGHT, fill=Y)
    elif 'w' in _mode:
        v_bar = Scrollbar(frame)
        v_bar.pack(side=LEFT, fill=Y)
    if 'n' in _mode:
        h_bar = Scrollbar(frame, orient=HORIZONTAL)
        h_bar.pack(side=TOP, fill=X)
    elif 's' in _mode:
        h_bar = Scrollbar(frame, orient=HORIZONTAL)
        h_bar.pack(side=BOTTOM, fill=X)

    if not v_bar and not h_bar:
        print('Bad mode:', _mode)
        return None
    widget=_class(frame, **_widget_opt)
    if v_bar:
        widget.config(yscrollcommand=v_bar.set)
        v_bar.config(command=widget.yview)
    if (h_bar):
        widget.config(xscrollcommand=h_bar.set)
        h_bar.config(command=widget.xview)
    widget.pack(fill=BOTH, expand=True)
    return widget

def setLogo(parent):
    try:
        logo_file = os.path.join(globalConfig.build_config['proj_root'], globalConfig.build_config['LOGO'])
        logo_photo = PhotoImage(file=logo_file)
        logo_photo = logo_photo.subsample(1, 1)
        logo = Label(parent, image=logo_photo)
        logo.image = logo_photo
        logo.pack(fill=BOTH, side=BOTTOM)
    except TclError:
        pass

class globalConfig:
    server = StringVar()
    Jobs = IntVar()
    Debug = IntVar()
    Arch = IntVar()
    Verbose = IntVar()
    build_config = {}
    variant = IntVar()
    description = StringVar()

    config_save_file = 'build_save.cfg'

    @classmethod
    def load_config(cls):
        cls.build_config = bcc.load_build_config(None, None)
        cls.archs = cls.build_config['TARGET_LIST'].keys()

        if cls.build_config['ret'] != 'ok':
            showerror('Config Error!', cls.build_config['ret'])
            exit(-1)
        def_arch = cls.build_config['DEFAULT_TARGET']
        cls.entry_var_map = { 'Jobs' : (cls.Jobs, 8),
                      'Debug': (cls.Debug, 0),
                      'Arch' : (cls.Arch, cls.archs.index(def_arch)),
                      'Verbose' : (cls.Verbose, 0),
                      'Variant' : (cls.variant, cls.build_config['VARIANT'][def_arch].index(cls.build_config['DEFAULT_VARIANT']))}
        try:
            fp = open(cls.config_save_file, 'r')
        except IOError:
            #print('Saved config file %s does not exist. Using default...'%(cls.config_save_file))
            for key in cls.entry_var_map:
                cls.entry_var_map[key][0].set(cls.entry_var_map[key][1])
        else:
            try:
                config = json.loads(fp.read())
            except ValueError:
                print('Saved config file %s is not in json format. Using default...'%(cls.config_save_file))
                for key in cls.entry_var_map:
                    cls.entry_var_map[key][0].set(cls.entry_var_map[key][1])
            else:
                fp.close()
                for key in config:
                    if (key in cls.entry_var_map):
                        cls.entry_var_map[key][0].set(config[key])

    @classmethod
    def save_config(cls):
        config = {}
        for key in cls.entry_var_map:
            config[key] = cls.entry_var_map[key][0].get();
        for key in cls.sys_config_map:
            config[key] = cls.sys_config_map[key]

        try:
            f = open(cls.config_save_file, 'w')
        except IOError:
            print('Cannot open %s for write!'%s())
        else:
            f.write(json.dumps(config, indent=4))
            f.close()

    @classmethod
    def get_arch(cls):
        return cls.archs[cls.Arch.get()]

    @classmethod
    def get_package(cls):
        return cls.build_config['BUILD'][cls.get_arch()][cls.get_variant()]['GRAPH']

    @classmethod
    def get_build_config(cls):
        return cls.build_config

    @classmethod
    def get_variant(cls):
        return cls.build_config['VARIANT'][cls.get_arch()][cls.variant.get()]

    @classmethod
    def set_description(cls):
        target_info = cls.build_config['TARGET_LIST'][cls.get_arch()]
        var_info = cls.build_config['VARIANT_LIST'][cls.get_variant()]
        desc = '##Target: %s\n'%(target_info['DESCRIPTION']) 
        desc += '##Variant: %s\nMacro: %s'%(var_info['DESCRIPTION'], var_info['MACRO']) 
        cls.description.set(desc)

class archZone:
    def __init__(self, parent):
        i = 0
        for arch in globalConfig.build_config['BUILD']:
            Radiobutton(parent, text=arch,
                        variable=globalConfig.Arch, value=globalConfig.archs.index(arch),
                        command=self.onSelected).pack(anchor=W)
            i += 1
    def onSelected(self):
        num_var = len(globalConfig.build_config['VARIANT'][globalConfig.get_arch()])
        if (num_var <= globalConfig.variant.get()):
            globalConfig.variant.set(num_var - 1)
        tk_service_list.populate(globalConfig.get_package())
        tk_service_build_list.populate([])
        variant_zone.populate()
        globalConfig.set_description()
class optionZone:
    def __init__(self, parent):
        Checkbutton(parent, text='-V', variable=globalConfig.Verbose).pack(side=LEFT)
        Checkbutton(parent, text='-g', variable=globalConfig.Debug).pack(side=LEFT)
        createLabelEntry(parent, 'Jobs', RIGHT, _entry_opt={'justify':CENTER,'width':2,'textvariable':globalConfig.Jobs})

class buildButton:
    def __init__(self, parent):
        self.build_bt = Button(parent, text='Build', command=self.onBuild)
        self.build_bt.pack(expand=True, side=TOP)

        self.clean_bt = Button(parent, text='Clean', command=self.onClean)
        self.clean_bt.pack(expand=True, side=TOP)
    def onBuild(self):
        if self.clean_bt.config('text')[-1] == 'Stop':
            showinfo('Note', 'Build after cleaning is done.')
        elif self.build_bt.config('text')[-1] == 'Build':
            if not bcc.build_cmd_pipe:
                cur_packages = [tk_service_build_list.lb.get(idx) for idx in tk_service_build_list.lb.curselection()]
                if cur_packages:
                    self.build_bt.config(text='Stop')
                    build_packages(cur_packages, globalConfig.get_build_config(), self.onOutput)
                else:
                    showinfo('Note', 'Please select packages and dependency before building.')
        else:
            if bcc.build_cmd_pipe:
                bcc.build_stop = 1
                self.build_bt.config(text='Build')
                bcc.build_cmd_pipe.kill()
                bcc.build_cmd_pipe.wait()
                bcc.build_cmd_pipe = None
    def onClean(self):
        if self.build_bt.config('text')[-1] == 'Stop':
            showinfo('Note', 'Clean after building is done.')
        elif self.clean_bt.config('text')[-1] == 'Clean':
            if not bcc.build_cmd_pipe:
                cur_packages = [tk_service_build_list.lb.get(idx) for idx in tk_service_build_list.lb.curselection()]
                if cur_packages:
                    self.clean_bt.config(text='Stop')
                    build_packages(cur_packages, globalConfig.get_build_config(), self.onOutput, True, True)
                else:
                    showinfo('Note', 'Please select packages and dependency before cleaning.')
        else:
            if bcc.build_cmd_pipe:
                bcc.build_stop = 1
                self.clean_bt.config(text='Clean')
                bcc.build_cmd_pipe.kill()
                bcc.build_cmd_pipe.wait()
                bcc.build_cmd_pipe = None
    def onOutput(self, line):
        global tk_message_box
        root.update()
        tk_message_box.insert(END, line)
        tk_message_box.see(END)

class variantZone:
    def __init__(self, parent):
        self.buttons = []
        self.parent = parent
        self.populate()
    def onSelected(self):
        tk_service_list.populate(globalConfig.get_package())
        tk_service_build_list.populate([])
        globalConfig.set_description()
    def populate(self):
        for radio in self.buttons:
            radio.destroy()
        self.buttons = []
        id = 0
        for variant in globalConfig.build_config['VARIANT'][globalConfig.get_arch()]:
            radio = Radiobutton(self.parent, text=variant,
                        variable=globalConfig.variant, value=id,
                        command=self.onSelected)
            radio.pack(anchor=W)
            self.buttons += [radio]
            id += 1

class messageButton:
    def __init__(self, parent):
        Button(parent, text='Log', command=self.onLog).pack(fill=BOTH, expand=True, side=TOP)
        Button(parent, text='Clean', command=self.onClean).pack(fill=BOTH, expand=True, side=TOP)
        Button(parent, text='Graph', command=self.onGraph).pack(fill=BOTH, expand=True, side=TOP)
    def onClean(self):
        tk_message_box.delete(1.0, END)
    def onLog(self):
        log_file = os.path.join(globalConfig.build_config['LOG_DIR'], globalConfig.get_arch(), 'log')
        if os.path.exists(log_file):
            os.system('gnome-terminal --maximize -- "vim ' + log_file + '"')
    def onGraph(self):
        draw_packages(globalConfig.build_config,
                         globalConfig.get_arch(),
                         globalConfig.get_variant())

class syncButton:
    def __init__(self, parent):
        Button(parent, text='Update', command=self.onBuild).pack(fill=BOTH, expand=True, side=LEFT)
    def onBuild(self):pass

class packageBuildList:
    def __init__(self, parent, package_list):
        self.lb = Scrolled(Listbox, parent, _mode='es', _widget_opt={'width':32,'height':15, 'exportselection':0, 'takefocus':0, 'selectmode':EXTENDED, 'selectborderwidth':2, 'borderwidth':4})
        self.lb.pack(fill=Y)
        self.populate(package_list)
        ctrl_frame = LabelFrame(parent, text='Select')
        ctrl_frame.pack(fill=BOTH, expand=True, side=BOTTOM)
        Button(ctrl_frame, text='All', command=self.onSelectAll).pack(fill=BOTH, expand=True, side=LEFT)
        Button(ctrl_frame, text='None', command=self.onSelectNone).pack(fill=BOTH, expand=True, side=LEFT)
    def populate(self, package_list):
        self.pkg_list = package_list
        self.lb.delete(0, END)
        for pkg in package_list:
            self.lb.insert(END, pkg)
    def onSelectAll(self):
        self.lb.selection_set(0, END)
    def onSelectNone(self):
        self.lb.selection_clear(0, END)

class packageList:
    def __init__(self, parent, package_list):
        self.lb = Scrolled(Listbox, parent, _mode='es', _widget_opt={'width':32,'height':18, 'exportselection':0, 'takefocus':1, 'selectmode':EXTENDED, 'selectborderwidth':2, 'borderwidth':4})
        self.lb.bind("<Double-Button-1>", self.onItemDoubleClick)
        self.lb.bind('<<ListboxSelect>>', self.onItemSelected)
        self.lb.pack(fill=Y)
        self.populate(package_list)
        # track all instances
    def populate(self, package_list):
        self.pkg_list = package_list
        self.lb.delete(0, END)
        all_target_found = False
        tmp_list = []
        for pkg in package_list:
            if pkg != bcc.build_all_target:
                tmp_list.append(pkg)
            else:
                all_target_found = True
        tmp_list.sort()
        if all_target_found:
            tmp_list.append(bcc.build_all_target)
        for pkg in tmp_list:
            self.lb.insert(END, pkg)
    def onItemDoubleClick(self, event):
        #showinfo('double click', 'item %s is selected.'%(self.lb.get(self.lb.curselection())))
        pass
    def onItemSelected(self, event):
        #cur_package = self.lb.get(self.lb.curselection())
        cur_packages = [self.lb.get(idx) for idx in self.lb.curselection()]
        build_list = []
        for pkg in cur_packages:
            bcc.generate_build_order(self.pkg_list, pkg, build_list)
        build_list.reverse()
        tk_service_build_list.populate(build_list)
        for pkg in cur_packages:
            tk_service_build_list.lb.selection_set(build_list.index(pkg))

class App:
    def __init__(self, master):

        frame = Frame(master)
        frame.pack(fill=BOTH, expand=True)

        msg_frame = Frame(frame)
        msg_frame.pack(side=BOTTOM, fill=X)
        service_frame = LabelFrame(frame, text='Packages')
        service_frame.pack(side=LEFT, fill=Y, expand=True)
        dependency_frame = LabelFrame(frame, text='Dependency')
        dependency_frame.pack(side=LEFT, fill=Y, expand=True)
        config_frame = Frame(frame)
        config_frame.pack(side=RIGHT, fill=Y)

        msg_window_frame = Frame(msg_frame)
        msg_window_frame.pack(side=LEFT, fill=BOTH)
        msg_button_frame = LabelFrame(msg_frame, text='Tools')
        msg_button_frame.pack(side=LEFT, fill=BOTH)
        global tk_message_box
        tk_message_box = Scrolled(Text, msg_window_frame, _mode='es',
                _pack_opt={'fill': X},
                _label_opt={'text': 'Message'},
                _widget_opt={'wrap': WORD, 'width': 92, 'height': message_window_height})
        messageButton(msg_button_frame)

        logo_frame = Frame(config_frame)
        logo_frame.pack(side=TOP, fill=BOTH)
        setLogo(logo_frame)

        variant_frame = LabelFrame(config_frame, text='Variant')
        variant_frame.pack(side=TOP, fill=X)
        global variant_zone
        variant_zone = variantZone(variant_frame)

        desc_frame = Frame(config_frame)
        desc_frame.pack(side=TOP, fill=X)
        globalConfig.set_description()
        Label(desc_frame, textvariable = globalConfig.description, wraplength = 188).pack(fill=BOTH, side=LEFT)

        build_frame = LabelFrame(config_frame, text='Build')
        build_frame.pack(side=BOTTOM, fill=X)
        arch_frame = Frame(build_frame)
        arch_frame.pack(side=LEFT, fill=X)
        archZone(arch_frame)
        build_button_frame = Frame(build_frame)
        build_button_frame.pack(side=RIGHT, fill=BOTH)
        global tk_build_button
        tk_build_button = buildButton(build_button_frame)
        global tk_service_list
        tk_service_list = packageList(service_frame, globalConfig.get_package())
        global tk_service_build_list
        tk_service_build_list = packageBuildList(dependency_frame, [])

        option_frame = LabelFrame(config_frame, text='Options')
        option_frame.pack(side=TOP, fill=X)
        optionZone(option_frame)


def set_window_info(window, name):
    xpos = int((window.winfo_screenwidth()  -  window_width) / 2)
    ypos = int((window.winfo_screenheight()  -  window_height) / 2)
    window.geometry('%dx%d+%d+%d'%(window_width,window_height,xpos,ypos))
    window.title(name);

globalConfig.load_config()
#globalConfig.save_config()

set_window_info(root, globalConfig.build_config['PROJECT_NAME'] + ' BuildCentral@' + globalConfig.build_config['proj_root'])

try:
    img = Image("photo", file=os.path.join(globalConfig.build_config['proj_root'], 'tools', 'buildCentral', 'icon.gif'))
    root.tk.call('wm', 'iconphoto', root._w, img)
except TclError:
    pass

def quit_check():
    root.after(200, quit_check)
app = App(root)
root.after(200, quit_check)
try:
    root.mainloop()
except:
    sys.exit(0)
