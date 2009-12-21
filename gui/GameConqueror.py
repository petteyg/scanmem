#!/usr/bin/env python
"""
    Game Conqueror: a graphical game cheating tool, using scanmem as its backend
    
    Copyright (C) 2009 Wang Lu <coolwanglu(a)gmail.com>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""


import sys
import os
import subprocess
import re

import pygtk
import gtk
import gobject

WORK_DIR = os.path.dirname(os.path.realpath(sys.argv[0]))
BACKEND = [WORK_DIR+'/../scanmem', '-b']
BACKEND_END_OF_OUTPUT_PATTERN = re.compile(r'(\d+)>\s*')
DATA_WORKER_INTERVAL = 500 # for read(update)/write(lock)
SCAN_RESULT_LIST_LIMIT = 1000 # maximal number of entries that can be displayed

# init data types
# convert [a,b,c] into a liststore that [[a],[b],[c]], where a,b,c are strings
def build_simple_str_liststore(l):
    r = gtk.ListStore(str)
    for e in l:
        r.append([e])
    return r

LOCK_FLAG_TYPES = build_simple_str_liststore(['=', '+', '-'])

LOCK_VALUE_TYPES = build_simple_str_liststore(['int'
                                            ,'int:1' 
                                            ,'int:2'
                                            ,'int:4'
                                            ,'int:8' 
                                            ,'float:4'
                                            ,'float:8'
                                            ])

# convert type names used by scanmem into ours
TYPENAMES_S2G = {'I64':'int:8'
                ,'I64s':'int:8'
                ,'I64u':'int:8'
                ,'I32':'int:4'
                ,'I32s':'int:4'
                ,'I16':'int:2'
                ,'I16s':'int:2'
                ,'I16u':'int:2'
                ,'I8':'int:1'
                ,'I8s':'int:1'
                ,'I8u':'int:1'
                ,'F32':'float:4'
                ,'F64':'float:8'
                }   

# typenams: gameconqueror-> scanmem
# signedness are lost!
TYPENAMES_G2S = {'int:8':'I64'
                ,'int:4':'I32'
                ,'int:2':'I16'
                ,'int:1':'I8'
                ,'float:4':'F32'
                ,'float:8':'F64'
                }

class GameConquerorBackend():
    def __init__(self):
        self.match_count = 0
        self.backend = subprocess.Popen(BACKEND, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        # read initial info
        self.get_output_lines()

    def get_output_lines(self):
        lines = []
        while True:
            line = self.backend.stdout.readline()
            match = BACKEND_END_OF_OUTPUT_PATTERN.match(line)
            if match is None:
                lines.append(line)
            else:
                self.match_count = int(match.groups()[0])
                break
        return lines

    def send_command(self, cmd):
        self.backend.stdin.write(cmd+'\n')
        output_lines = self.get_output_lines()
        # for debug
#        print '\n'.join(output_lines)
        return output_lines

    # for test only
    def run(self):
        while True:
            print '\n'.join(self.get_output_lines())
            l = sys.stdin.readline()
            self.backend.stdin.write(l)


        

class GameConqueror():
    def __init__(self):
        ##################################
        # init GUI
        self.builder = gtk.Builder()
        self.builder.add_from_file(os.path.join(WORK_DIR, 'GameConqueror.xml'))

        self.main_window = self.builder.get_object('MainWindow')
        self.about_dialog = self.builder.get_object('AboutDialog')
        self.process_list_dialog = self.builder.get_object('ProcessListDialog')

        self.found_count_label = self.builder.get_object('FoundCount_Label')
        self.process_label = self.builder.get_object('Process_Label')
        self.value_input = self.builder.get_object('Value_Input')

        self.scan_button = self.builder.get_object('Scan_Button')
        self.reset_button = self.builder.get_object('Reset_Button')

        self.search_integer_checkbutton = self.builder.get_object('SearchInteger_CheckButton')
        self.search_float_checkbutton = self.builder.get_object('SearchFloat_CheckButton')

        # init scanresult treeview
        # we may need a cell data func here
        # create model
        self.scanresult_tv = self.builder.get_object('ScanResult_TreeView')
        self.scanresult_liststore = gtk.ListStore(str, str, str) 
        self.scanresult_tv.set_model(self.scanresult_liststore)
        # first column
        self.scanresult_tv_col1 = gtk.TreeViewColumn('Address')
        self.scanresult_tv.append_column(self.scanresult_tv_col1)
        self.scanresult_tv_col1_renderer = gtk.CellRendererText()
        self.scanresult_tv_col1.pack_start(self.scanresult_tv_col1_renderer, True)
        self.scanresult_tv_col1.set_attributes(self.scanresult_tv_col1_renderer, text=0)
        # second column
        self.scanresult_tv_col2 = gtk.TreeViewColumn('Value')
        self.scanresult_tv.append_column(self.scanresult_tv_col2)
        self.scanresult_tv_col2_renderer = gtk.CellRendererText()
        self.scanresult_tv_col2.pack_start(self.scanresult_tv_col2_renderer, True)
        self.scanresult_tv_col2.set_attributes(self.scanresult_tv_col2_renderer, text=1)
        # for debug
#        self.scanresult_liststore.append(['0','1'])
#        self.scanresult_liststore.append(['2','3'])

        # TODO init CheatList TreeView
        self.cheatlist_tv = self.builder.get_object('CheatList_TreeView')
        self.cheatlist_liststore = gtk.ListStore(str, bool, str, str, str, str)
        self.cheatlist_tv.set_model(self.cheatlist_liststore)
        # zeroth column - Lock Flag
        self.cheatlist_tv_col0 = gtk.TreeViewColumn('')
        self.cheatlist_tv.append_column(self.cheatlist_tv_col0)
        self.cheatlist_tv_col0_renderer = gtk.CellRendererCombo()
        self.cheatlist_tv_col0.pack_start(self.cheatlist_tv_col0_renderer, True)
        self.cheatlist_tv_col0.set_attributes(self.cheatlist_tv_col0_renderer, text=0)
        self.cheatlist_tv_col0_renderer.set_property('editable', True)
        self.cheatlist_tv_col0_renderer.set_property('has-entry', False)
        self.cheatlist_tv_col0_renderer.set_property('model', LOCK_FLAG_TYPES)
        self.cheatlist_tv_col0_renderer.set_property('text-column', 0)
        self.cheatlist_tv_col0_renderer.connect('edited', self.cheatlist_toggle_lock_flag_cb)
        # first column - Lock
        self.cheatlist_tv_col1 = gtk.TreeViewColumn('Lock')
        self.cheatlist_tv.append_column(self.cheatlist_tv_col1)
        self.cheatlist_tv_col1_renderer = gtk.CellRendererToggle()
        self.cheatlist_tv_col1.pack_start(self.cheatlist_tv_col1_renderer, True)
        self.cheatlist_tv_col1_renderer.set_property('activatable', True)
        self.cheatlist_tv_col1_renderer.set_property('radio', False)
        self.cheatlist_tv_col1_renderer.set_property('inconsistent', False)
        self.cheatlist_tv_col1_renderer.set_property('activatable', True)
        self.cheatlist_tv_col1_renderer.connect('toggled', self.cheatlist_toggle_lock_cb)
        self.cheatlist_tv_col1.set_attributes(self.cheatlist_tv_col1_renderer, active=1)
        # second column - Description
        self.cheatlist_tv_col2 = gtk.TreeViewColumn('Description')
        self.cheatlist_tv.append_column(self.cheatlist_tv_col2)
        self.cheatlist_tv_col2_renderer = gtk.CellRendererText()
        self.cheatlist_tv_col2.pack_start(self.cheatlist_tv_col2_renderer, True)
        self.cheatlist_tv_col2_renderer.set_property('editable', True)
        self.cheatlist_tv_col2_renderer.connect('edited', self.cheatlist_edit_description_cb)
        self.cheatlist_tv_col2.set_attributes(self.cheatlist_tv_col2_renderer, text=2)
        # third column - Address
        self.cheatlist_tv_col3 = gtk.TreeViewColumn('Address')
        self.cheatlist_tv.append_column(self.cheatlist_tv_col3)
        self.cheatlist_tv_col3_renderer = gtk.CellRendererText()
        self.cheatlist_tv_col3.pack_start(self.cheatlist_tv_col3_renderer, True)
        self.cheatlist_tv_col3.set_attributes(self.cheatlist_tv_col3_renderer, text=3)
        # fourth column - Type
        self.cheatlist_tv_col4 = gtk.TreeViewColumn('Type')
        self.cheatlist_tv.append_column(self.cheatlist_tv_col4)
        self.cheatlist_tv_col4_renderer = gtk.CellRendererCombo()
        self.cheatlist_tv_col4.pack_start(self.cheatlist_tv_col4_renderer, True)
        self.cheatlist_tv_col4.set_attributes(self.cheatlist_tv_col4_renderer, text=4)
        self.cheatlist_tv_col4_renderer.set_property('editable', True)
        self.cheatlist_tv_col4_renderer.set_property('has-entry', False)
        self.cheatlist_tv_col4_renderer.set_property('model', LOCK_VALUE_TYPES)
        self.cheatlist_tv_col4_renderer.set_property('text-column', 0)
        self.cheatlist_tv_col4_renderer.connect('edited', self.cheatlist_edit_type_cb)
        # fifth column - Value 
        self.cheatlist_tv_col5 = gtk.TreeViewColumn('Value')
        self.cheatlist_tv.append_column(self.cheatlist_tv_col5)
        self.cheatlist_tv_col5_renderer = gtk.CellRendererText()
        self.cheatlist_tv_col5.pack_start(self.cheatlist_tv_col5_renderer, True)
        self.cheatlist_tv_col5_renderer.set_property('editable', True)
        self.cheatlist_tv_col5_renderer.connect('edited', self.cheatlist_edit_value_cb)
        self.cheatlist_tv_col5.set_attributes(self.cheatlist_tv_col5_renderer, text=5)
        # for debug
#        self.cheatlist_liststore.append(['+', True, '2', '3', '4', '5'])
#        self.cheatlist_liststore.append([' ', False, 'desc', 'addr', 'type', 'value'])

        # init ProcessList_TreeView
        self.processlist_tv = self.builder.get_object('ProcessList_TreeView')
        self.processlist_tv.get_selection().set_mode(gtk.SELECTION_SINGLE)
        self.processlist_liststore = gtk.ListStore(str, str)
        self.processlist_tv.set_model(self.processlist_liststore)
        self.processlist_tv.set_enable_search(True)
        self.processlist_tv.set_search_column(1)
        # first col
        self.processlist_tv_col1 = gtk.TreeViewColumn('PID')
        self.processlist_tv.append_column(self.processlist_tv_col1)
        self.processlist_tv_col1_renderer = gtk.CellRendererText()
        self.processlist_tv_col1.pack_start(self.processlist_tv_col1_renderer, True)
        self.processlist_tv_col1.set_attributes(self.processlist_tv_col1_renderer, text=0)
        # second col
        self.processlist_tv_col2 = gtk.TreeViewColumn('Process')
        self.processlist_tv.append_column(self.processlist_tv_col2)
        self.processlist_tv_col2_renderer = gtk.CellRendererText()
        self.processlist_tv_col2.pack_start(self.processlist_tv_col2_renderer, True)
        self.processlist_tv_col2.set_attributes(self.processlist_tv_col2_renderer, text=1)

        # init popup menu for scanresult
        self.scanresult_popup = gtk.Menu()
        self.scanresult_popup_item1 = gtk.MenuItem("Add to cheat list")
        self.scanresult_popup.append(self.scanresult_popup_item1)
        self.scanresult_popup_item1.connect('activate', self.scanresult_popup_cb, 'add_to_cheat_list')
        self.scanresult_popup.show_all()

        self.builder.connect_signals(self)
        self.main_window.connect('destroy', self.exit)

        ###########################
        # init others (backend, flag...)

        self.backend = GameConquerorBackend()
        self.search_count = 0
        self.exit_flag = False # currently for data_worker only, other 'threads' may also use this flag
        gobject.timeout_add(DATA_WORKER_INTERVAL, self.data_worker)

    ###########################
    # GUI callbacks

    def ValueHelp_Button_clicked_cb(self, button, Data=None):
        # show value help dialog
        dialog = gtk.MessageDialog(None
                                 ,0
                                 ,gtk.MESSAGE_INFO
                                 ,gtk.BUTTONS_OK
                                 ,'Currently use any scanmem (scan) command here.\nI\'m considering using some more complicated but convenient syntax later (like 255:4, 5-7, >, <=, etc.)\nTherefore the parsing could be done in the frontend, while backend can still use standard forms')
        dialog.run()
        dialog.destroy()

    def Value_Input_activate_cb(self, entry, data=None):
        self.do_scan()
        return True

    def ScanResult_TreeView_button_release_event_cb(self, widget, event, data=None):
        if event.button == 3: # right click
            (model, iter) = self.scanresult_tv.get_selection().get_selected()
            if iter is not None:
                self.scanresult_popup.popup(None, None, None, event.button, event.get_time())
                return True
            return False
        return False

    def ScanResult_TreeView_popup_menu_cb(self, widget, data=None):
        (model, iter) = self.scanresult_tv.get_selection().get_selected()
        if iter is not None:
            self.scanresult_popup.popup(None, None, None, 0, 0)
            return True
        return False


    def ScanResult_TreeView_row_activated_cb(self, treeview, path, view_column, data=None):
        # add to cheat list
        (model, iter) = self.scanresult_tv.get_selection().get_selected()
        if iter is not None:
            (addr, value, typestr) = model.get(iter, 0, 1, 2)
            self.add_to_cheat_list(addr, value, typestr)
            return True
        return False

    def ProcessList_TreeView_row_activated_cb(self, treeview, path, view_column, data=None):
        (model, iter) = self.processlist_tv.get_selection().get_selected()
        if iter is not None:
            (pid, process) = model.get(iter, 0, 1)
            self.select_process(int(pid), process)
            self.process_list_dialog.response(gtk.RESPONSE_CANCEL)
            return True
        return False

    def SelectProcess_Button_clicked_cb(self, button, data=None):
        self.processlist_liststore.clear()
        pl = self.get_process_list()
        for p in pl:
            self.processlist_liststore.append([p[0], p[1][:50]]) # limit the length here, otherwise it may crash (why?)
        self.process_list_dialog.show()
        while True:
            res = self.process_list_dialog.run()
            if res == gtk.RESPONSE_OK: # -5
                (model, iter) = self.processlist_tv.get_selection().get_selected()
                if iter is None:
                    dialog = gtk.MessageDialog(None
                                     ,gtk.DIALOG_MODAL
                                     ,gtk.MESSAGE_ERROR
                                     ,gtk.BUTTONS_OK
                                     ,'Please select a process')
                    dialog.run()
                    dialog.destroy()
                    continue
                else:
                    (pid, process) = model.get(iter, 0, 1)
                    self.select_process(int(pid), process)
                    break
            else: # for None and Cancel
                break
        self.process_list_dialog.hide()
        return True

    def Scan_Button_clicked_cb(self, button, data=None):
        self.do_scan()
        return True

    def Reset_Button_clicked_cb(self, button, data=None):
        self.reset_scan()
        return True

    def ScanType_ComboBox_changed_cb(self, combobox, data=None):
        return True 

    def ValueType_ComboBox_changed_cb(self, combobox, data=None):
        return True 

    def Logo_EventBox_button_release_event_cb(self, widget, data=None):
        self.about_dialog.run()
        self.about_dialog.hide()
        return True

    #######################3
    # renamed callbacks
    # (i.e. not standard event names are used)
    
    def scanresult_popup_cb(self, menuitem, data=None):
        if data == 'add_to_cheat_list':
            (model, iter) = self.scanresult_tv.get_selection().get_selected()
            if iter is not None:
                (addr, value, typestr) = model.get(iter, 0, 1, 2)
                self.add_to_cheat_list(addr, value, typestr)
                return True
            return False
        return False

    def cheatlist_toggle_lock_cb(self, cellrenderertoggle, path, data=None):
        row = int(path)
        locked = self.cheatlist_liststore[row][1]
        locked = not locked
        self.cheatlist_liststore[row][1] = locked
        if locked:
            #TODO: check value(valid number & not overflow), if failed, unlock it and do nothing
            pass
        else:
            #TODO: update its value?
            pass
        return True

    def cheatlist_toggle_lock_flag_cb(self, cell, path, new_text, data=None):
        row = int(path)
        self.cheatlist_liststore[row][0] = new_text
        # data_worker will handle this later
        return True

    def cheatlist_edit_description_cb(self, cell, path, new_text, data=None):
        row = int(path)
        self.cheatlist_liststore[row][2] = new_text
        return True

    def cheatlist_edit_value_cb(self, cell, path, new_text, data=None):
        row = int(path)
        self.cheatlist_liststore[row][5] = new_text
        if self.cheatlist_liststore[row][1]: # locked
            # data_worker will handle this
            pass
        else:
            # write it for once
            (lockflag, locked, desc, addr, typestr, value) = self.cheatlist_liststore[row]
            self.write_value(addr, typestr, value)
        return True

    def cheatlist_edit_type_cb(self, cell, path, new_text, data=None):
        row = int(path)
        self.cheatlist_liststore[row][4] = new_text
        if self.cheatlist_liststore[row][1]: # locked
            # false unlock it
            self.cheatlist_liststore[row][1] = False
            pass
        # TODO may need read & update (reinterpret) the value
        return True

    ############################
    # core functions

    def add_to_cheat_list(self, addr, value, typestr):
        # determine longest possible type
        types = typestr.split()
        for t in types:
            if TYPENAMES_S2G.has_key(t):
                vt = TYPENAMES_S2G[t]
                break
        self.cheatlist_liststore.prepend(['=', False, 'No Description', addr, vt, value])
        # TODO: watch this item

    def get_process_list(self):
        return [e.strip().split(' ',1) for e in os.popen('ps -wweo pid=,command= --sort=-pid').readlines()]

    def select_process(self, pid, process_name):
        # ask backend for attaching the target process
        # update 'current process'
        # reset flags
        print 'Select process: %d - %s' % (pid, process_name)
        self.process_label.set_text('%d - %s' % (pid, process_name))
        self.backend.send_command('pid %d' % (pid,))
        self.reset_scan()
        # unlock all entries in cheat list
        for i in xrange(len(self.cheatlist_liststore)):
            self.cheatlist_liststore[i][1] = False

    def reset_scan(self):
        self.search_count = 0
        # reset search type and value type
        self.scanresult_liststore.clear()
        self.backend.send_command('reset')

    # perform scanning through backend
    # set GUI if needed
    def do_scan(self):
        # set scan options
        self.backend.send_command('option search_integer %s' % ((self.search_integer_checkbutton.get_property('active') and '1' or '0'),))
        self.backend.send_command('option search_float %s' % ((self.search_float_checkbutton.get_property('active') and '1' or '0'),))
        # TODO: syntax check
        self.backend.send_command(self.value_input.get_text())
        self.update_scan_result()
        self.search_count +=1 
 
    def update_scan_result(self):
        self.found_count_label.set_text('Found: %d' % (self.backend.match_count,))
        if (self.backend.match_count > SCAN_RESULT_LIST_LIMIT):
            self.scanresult_liststore.clear()
        else:
            lines = self.backend.send_command('list')
            self.scanresult_tv.set_model(None)
            # temporarily disable model for scanresult_liststore for the sake of performance
            self.scanresult_liststore.clear()
            for line in lines:
                line = line[line.find(']')+1:]
                (a, v, t) = map(str.strip, line.split(',')[:3])
                t = t[1:-1]
                self.scanresult_liststore.append([a, v, t])
            self.scanresult_tv.set_model(self.scanresult_liststore)

    # return (r1, r2) where all rows between r1 and r2 (INCLUSIVE) are visible
    # return None if no row visible
    def get_visible_rows(self, treeview):
        rect = treeview.get_visible_rect()
        (x1,y1) = treeview.tree_to_widget_coords(rect.x,rect.y)
        (x2,y2) = treeview.tree_to_widget_coords(rect.x+rect.width,rect.y+rect.height)
        tup = treeview.get_path_at_pos(x1, y1)
        if tup is None:
            return None
        r1 = tup[0][0]
        tup = treeview.get_path_at_pos(x2, y2)
        if tup is None:
            r2 = len(treeview.get_model()) - 1    
        else:
            r2 = tup[0][0]
        return (r1, r2)
 
    # read/write data periodly
    def data_worker(self):
        rows = self.get_visible_rows(self.scanresult_tv)
        if rows is not None:
            (r1, r2) = rows # [r1, r2] rows are visible
            # TODO: update some part of scanresult
        # TODO read unlocked values in cheat list
        # write locked values in cheat list
        for i in xrange(len(self.cheatlist_liststore)):
            (lockflag, locked, desc, addr, typestr, value) = self.cheatlist_liststore[i]
            if locked:
                self.write_value(addr, typestr, value)
        return not self.exit_flag

    # typestr: use our typenames
    def write_value(self, addr, typestr, value):
        self.backend.send_command('write %s %s %s'%(TYPENAMES_G2S[typestr], addr, value))

    def exit(self, object, data=None):
        self.exit_flag = True
        gtk.main_quit()

    def main(self):
        gtk.main()

    

if __name__ == '__main__':
    GameConqueror().main()