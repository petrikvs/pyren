#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import gc
import re
import os
import datetime
import copy
import time
import subprocess
from pathlib import Path

from mod_utils import *
import mod_db_manager

# import traceback

try:
    # Python2
    import tkinter as tk
    import tkinter.ttk
    import tkinter.font
    import tkinter.messagebox
    import tkinter.filedialog
    import tkinter.simpledialog
    
except ImportError:
    # Python3
    import tkinter as tk
    import tkinter.ttk as ttk
    import tkinter.font
    import tkinter.messagebox
    import tkinter.filedialog

import mod_globals
from mod_elm import AllowedList
from mod_elm import dnat
from mod_elm import pyren_time
import xml.etree.ElementTree as et

class screenSettings ():  # for future use.
    geometry = ''  # main window geometry
    scf = 1.0  # font scale coefficient

class ButtonConfirmationDialog (tkinter.simpledialog.Dialog):
    def __init__(self, parent, text):
        self.top = tk.Toplevel (parent)
        self.top.title ('Please confirm')
        self.top.geometry ("450x450+50+50")
        self.top.bind ('<Escape>', self.no)
        self.confirm = False
        
        txt = tk.Text (self.top, relief=tk.GROOVE, borderwidth=1, wrap="none")  # , width=190, heigth=180
        txt.insert (tk.END, text + '\n')
        txt.pack (side=tk.TOP, padx=5, pady=5, expand=True, fill='both')
        
        frame = tk.Frame (self.top)
        frame.pack (side=tk.BOTTOM)
        
        byes = tk.Button (frame, text="YES", command=self.yes)
        byes.pack (side=tk.LEFT, padx=5, pady=5)
        
        bno = tk.Button (frame, text="NO", command=self.no)
        bno.pack (side=tk.RIGHT, padx=5, pady=5)
    
    def no(self):
        self.top.destroy ()
        self.confirm = False
    
    def yes(self):
        self.top.destroy ()
        self.confirm = True
    
    def show(self):
        self.top.deiconify ()
        self.top.wait_window ()
        return self.confirm

class InfoDialog (tkinter.simpledialog.Dialog):

    orig_text = ''

    def __init__(self, parent, text, hnid=False ):

        self.orig_text = text

        self.top = tk.Toplevel (parent)
        self.top.title ('Info')
        self.top.geometry ("800x500+50+50")
        self.top.bind ('<Escape>', self.close)
        
        self.txt = tk.Text (self.top, relief=tk.GROOVE, borderwidth=1, wrap="none")
        self.txt.insert (tk.END, text + '\n')
        self.txt.pack (side=tk.TOP, padx=5, pady=5, expand=True, fill='both')
        # txt.config(state=tk.DISABLED)
        
        b = tk.Button (self.top, text="Close", command=self.close)
        b.pack (side=tk.BOTTOM, padx=5, pady=5)

        b2 = tk.Button (self.top, text="Save", command=self.save)
        b2.pack (side=tk.BOTTOM, padx=5, pady=5)

        if hnid:
          b1 = tk.Button (self.top, text="Hide 'None'", command=self.hnid_func)
          b1.pack (side=tk.BOTTOM, padx=5, pady=5)

        # self.initial_focus.focus_set()
    
    def close(self):
        self.top.destroy ()

    def save(self):
        f = tkinter.filedialog.asksaveasfile(mode='w')
        if f is None:
            return
        text2save = str(self.txt.get(1.0, tk.END))
        f.write(text2save)
        f.close()

    def hnid_func(self):
        self.txt.delete('1.0', tk.END)
        for t in self.orig_text.split('---\n'):
            if mod_globals.none_val not in t:
                self.txt.insert(tk.END, t + '---\n')

class FindDialog (tkinter.simpledialog.Dialog):
    def __init__(self, parent, ecu ):

        self.ecu = ecu
        self.choise = ''

        self.top = tk.Toplevel (parent)
        self.top.title ('Find Dialog')
        self.top.geometry ("500x300+50+50")
        self.top.bind ('<Escape>', self.close)

        topFrame = tk.Frame (self.top)
        topFrame.pack(side=tk.TOP, expand=False, fill='x')

        self.pattern = ''
        self.findEnt = tk.Entry(topFrame, relief=tk.GROOVE, borderwidth=1, textvariable=self.pattern)
        self.findEnt.pack (side=tk.LEFT, expand=True, fill='both')
        tk.Button (topFrame, text='Find', command=self.find).pack (side=tk.RIGHT)
        self.findEnt.bind('<Return>', self.find)

        mdlFrame = tk.Frame (self.top)
        mdlFrame.pack(side=tk.BOTTOM, expand=True, fill='both')

        self.listBox = tk.Listbox(mdlFrame)
        self.listBox.pack (side=tk.BOTTOM, padx=5, pady=5, expand=True, fill='both')
        self.listBox.bind('<Double 1>', self.double_click)

        self.find()

    def double_click( self, event = '' ):
        self.choise = self.listBox.get(self.listBox.curselection())
        if '@' in self.choise:
            #self.choise = self.choise.split('@')[0]
            self.top.destroy ()
            return self.choise

    def find(self, event = '' ):

        ns = {'ns0': 'http://www-diag.renault.com/2002/ECU',
              'ns1': 'http://www-diag.renault.com/2002/screens'}

        self.listBox.delete( 0, tk.END )
        self.pattern = self.findEnt.get()

        for k in self.ecu.screen.Screens.keys():
            scr = self.ecu.screen.Screens[k]
            
            delym = '@'

            try:
                if type(scr) is not str:
                    scrName = scr.attrib['Name']
                    displays = scr.findall ("ns1:Display", ns)
                    for displ in displays:
                        DataName = displ.attrib["DataName"]
                        RequestName = displ.attrib["RequestName"]
                        line = k + delym + scrName + '/' + RequestName + '/' + DataName
                        if self.pattern in line:
                            self.listBox.insert (tk.END, line )
                else:
                    scrName = scr
                    if scr in self.ecu.requests.keys():
                        for rdi in self.ecu.requests[scr].ReceivedDI.keys():
                            line = k + delym + scrName + '/' + scr + '/' + rdi
                            if self.pattern in line:
                                self.listBox.insert (tk.END, line )
                                self.listBox.itemconfig(tk.END, {'bg' : 'yellow'})
                        for sdi in self.ecu.requests[scr].SentDI.keys():
                            line = k + delym + scrName + '/' + scr + '/' + sdi
                            if self.pattern in line:
                                self.listBox.insert (tk.END, line )
                                self.listBox.itemconfig(tk.END, {'bg' : 'yellow'})

            except:
                print( 'Find Exception ' + scr )

    def show(self):
        self.top.deiconify ()
        self.top.wait_window ()
        return self.choise
    
    def close(self):
        self.choise = ''
        self.top.destroy ()
       
class ListDialog (tkinter.simpledialog.Dialog):
    def __init__(self, parent, text, arr ):
        self.top = tk.Toplevel (parent)
        self.top.title (text)
        self.top.geometry ("500x300+50+50")
        self.top.bind ('<Escape>', self.close)

        self.L = tk.Listbox (self.top)
        for i in arr:
            self.L.insert (tk.END, i)
        self.L.pack (side=tk.TOP, padx=5, pady=5, expand=True, fill='both')

        b_fr = tk.Frame (self.top)
        b_fr.pack (side=tk.BOTTOM)
        
        tk.Button (b_fr, text='Close', command=self.close).pack (side=tk.LEFT)
        tk.Button (b_fr, text='Other', command=self.other).pack (side=tk.RIGHT)
        tk.Button (b_fr, text='Load', command=self.load).pack (side=tk.RIGHT)

    def close(self):
        self.choise = ''
        self.top.destroy ()

    def other(self):
        f = tkinter.filedialog.askopenfile(mode='r')
        if f is None:
            return
        self.choise = f.name
        self.top.destroy ()

    def load(self):
        self.choise = self.L.get(self.L.curselection())
        self.top.destroy ()

    def show(self):
        self.top.deiconify ()
        self.top.wait_window ()
        return self.choise

class DDTScreen (tk.Frame):
    tl = 0
    updatePeriod = 50
    decu = None
    xmlName = ''
    Screens = {}
    dDisplay = {}
    dValue = {}  # display value indexed by DataName
    iValue = {}  # input   value indexed by DataName
    iValueNeedUpdate = {}
    dReq = {}  # request names
    sReq_dl = {}  # delays for requests sent thru starting the screen
    sReq_lst = []  # list of requests sent thru starting the screen (order is important)
    dBtnSend = {}
    dFrames = []
    dObj = []  # objects for place_forget
    tObj = {}  # objects for text captions
    start = True
    csv = False
    csv_file = None
    sortedValueKeys = []
    csvValues = {}
    
    jid = None  # for after_cancel
    jdsu = None
    
    firstResize = False
    prefer_ECU = True  # type would be changed
    
    currentscreen = None
    
    scf = 1.0  # font scale factor
    
    def __init__(self, ddtFileName, xdoc, decu, top = False):
        
        self.xmlName = ddtFileName
        self.xdoc = xdoc
        
        # init local variables
        self.Screens = {}
        self.ScreensMenu = {}
        # self.Labels  = {}
        self.decu = decu
        self.decu.screen = self
        
        # init window
        if top:
            self.root = tk.Toplevel()
        else:
            self.root = tk.Tk()

        self.root.option_add ('*Dialog.msg.font', r'Courier\ New 12')
        # self.root.overrideredirect(True)
        self.root.geometry ("1024x768")
        tk.Frame.__init__ (self, self.root)
        self.root.bind ('<plus>', self.fontUp)
        self.root.bind ('<equal>', self.fontUp)
        self.root.bind ('<minus>', self.fontDown)
        
        # self.root.wm_attributes('-fullscreen', 1)
        
        self.translated = tk.BooleanVar ()
        self.translated.set (True)
        
        self.expertmode = tk.BooleanVar ()
        self.expertmode.set (mod_globals.opt_exp)
        
        self.approve = tk.BooleanVar ()
        self.approve.set (True)
        
        self.prefer_ECU = tk.BooleanVar ()
        self.prefer_ECU.set (True)

        clearScreen ()
        
        # clear elm cache
        self.decu.clearELMcache()

        self.initUI ()
        self.decu.initRotary()  #start thread doing periodic updates
        self.updateScreen ()
        self.root.focus_force ()
        self.root.mainloop ()
        
        #del(self.decu)
    
    def __del__(self):
        try:
            self.exit()
            gc.collect()
        except:
            pass
        
    def update_dInputs(self):
        for i in list(self.iValueNeedUpdate.keys()):
            self.iValueNeedUpdate[i] = True

    def updateScreenValues(self, req, rsp ):
        
        #debug
        #print '\nreq:', req
        #print 'rsp:', rsp

        if req is None or rsp is None:
            return

        request_list = []
        # find appropriate request
        if self.decu.req4sent[req] in list(self.decu.requests.keys()):
            r = self.decu.requests[self.decu.req4sent[req]]
            for k in list(self.decu.requests.keys()):
                if self.decu.requests[k].SentBytes == req:
                    request_list.append(self.decu.requests[k])
        else:
            return
        
        for request in request_list:
            if (any(key in list(request.ReceivedDI.keys()) for key in list(self.dValue.keys())) or 
                any(key in list(request.ReceivedDI.keys()) for key in list(self.iValue.keys()))):
                r = request

        tmstr = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.addToLog(tmstr + '>' + req + '  Rcvd:' + rsp)

        # update all variables from ReceivedDI
        for d in list(r.ReceivedDI.keys()):
    
            if d not in list(self.dValue.keys ()) and d not in list(self.iValue.keys()):
                continue
                
            val = self.decu.getValue (d)

            # update variable in dValue
            if d in list(self.dValue.keys()):
                if ':' in val:
                    _cv,_dv = val.split(':', maxsplit=1)
                    self.dValue[d].set(_dv)
                    self.csvValues[d] = _cv
                else:
                    self.dValue[d].set(val)
                    self.csvValues[d] = val
            
            # update variable in dInputs
            if d in list(self.iValue.keys()) and self.iValueNeedUpdate[d]:
                if self.prefer_ECU.get():
                    if len(self.decu.datas[d].List) or self.decu.datas[d].BytesASCII or self.decu.datas[d].Scaled:
                        self.iValue[d].set(val)
                    else:
                        val = self.decu.getHex(d)
                        if val!=mod_globals.none_val:
                            val = '0x' + val
                        self.iValue[d].set(val)

                else:
                    cmd = self.decu.cmd4data[d]
                    val = self.decu.getValue(d, request=self.decu.requests[cmd],
                                             responce=self.decu.requests[cmd].SentBytes)
                    if len(self.decu.datas[d].List) or self.decu.datas[d].BytesASCII or self.decu.datas[d].Scaled:
                        self.iValue[d].set(val)
                    else:
                        val = self.decu.getHex(d, request=self.decu.requests[cmd],
                                               responce=self.decu.requests[cmd].SentBytes)
                        if val!=mod_globals.none_val:
                            val = '0x' + val
                        self.iValue[d].set(val)
                self.iValueNeedUpdate[d] = False

    def updateScreen(self):
        '''Send periodic requests and get new data from ELM'''

        if self.decu:
            self.decu.rotaryRunAlloved.set()
        else:
            return

        # push new job when previous done
        if self.decu.rotaryCommandsQueue.empty():

            # push all req with no ManuelSend to queue
            for r in list(self.dReq.keys ()):
    
                if self.dReq[r]:  # manualSend
                     continue
                    
                req = self.decu.requests[r].SentBytes

                # not expert mode protection
                if (req[:2] not in AllowedList) and not mod_globals.opt_exp:
                    tmstr = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    self.addToLog (tmstr + ' Req:' + req + ' rejected due to non expert mode')
                    continue

                self.decu.putToRotary(req)

        tb = pyren_time()

        # read results
        while not self.decu.rotaryResultsQueue.empty():

            # no longer then 100ms
            if pyren_time()-tb > 0.1:
                break

            # get from input queue
            (req,rsp) = self.decu.rotaryResultsQueue.get_nowait()
            # request values update
            self.updateScreenValues(req,rsp)
        
        # write to csv
        if self.csv and self.csv_file!=None:
            csv_str = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            for k in self.sortedValueKeys:
                if k in self.csvValues.keys():
                    csv_str += ('\t' + self.csvValues[k])
                else:
                    csv_str += '\tNaN'
            csv_str += '\n'
            self.csv_file.write(csv_str)
            self.csv_file.flush()

        # re-launch update in "updatePeriod" milliseconds
        tb = pyren_time()
        self.jid = self.root.after (self.updatePeriod, self.updateScreen)
        self.tl = tb
    
    def startScreen(self):
        '''Send requests during starting of the screen'''
        
        self.decu.rotaryRunAlloved.set()

        # execute all req with no ManuelSend
        self.addToLog ('#Starting screen')
        for r in self.sReq_lst:
            req = self.decu.requests[r].SentBytes
            
            # not expert mode protection
            if (req[:2] not in ['10'] + AllowedList) and not mod_globals.opt_exp:
                self.addToLog ('Request:' + req + ' rejected due to non expert mode')
                continue

            self.decu.putToRotary(req)

        self.addToLog ('#Finish starting screen')
        
    
    def buttonPressed(self, btn, key):
        self.addToLog ('Button pressed:' + btn)
        
        # stop periodic requests
        if self.jid is not None:
            self.root.after_cancel (self.jid)
        self.decu.rotaryRunAlloved.clear()
        
        # clear elm cache
        self.decu.clearELMcache ()
        
        # prepare list of commands
        if key in list(self.dBtnSend.keys ()):
            sends = self.dBtnSend[key]
        else:
            return
        
        # pack DataItems to command
        slist = []  # list of smap
        smap = {}  # {'d':delay, 'c':sendCmd, 'r':requestInstance}
        error = False
        
        for send in sends:
            delay = send['Delay']
            requestName = send['RequestName']
            r = self.decu.requests[requestName]
            
            sendCmd = self.decu.packValues (requestName, self.iValue)
            if 'ERROR' in sendCmd:
                #print sendCmd
                self.addToLog (sendCmd)
                error = True
            smap['d'] = delay
            smap['c'] = sendCmd
            smap['r'] = r
            slist.append (copy.deepcopy (smap))
        
        # show confirmation dialog if approve is True
        confirmed = True
        if not error and self.approve.get ():
            commandSet = '\n\n'
            for c in slist:
                commandSet += "%-10s Delay:%-3s (%s)\n" % (c['c'], c['d'], c['r'].Name)
            confirmed = ButtonConfirmationDialog (self.root, commandSet).show ()
        
        # send commands
        if not error and confirmed:
            self.addToLog ('#Starting command execution')
            for c in slist:
                rsp = '00'
                
                # protection for debug period
                if mod_globals.opt_exp:
                    rsp = self.decu.elmRequest (c['c'], c['d'], cache=False)
                else:
                    rsp = r.ReplyBytes.replace (' ', '')
                    rsp = ' '.join (a + b for a, b in zip (rsp[::2], rsp[1::2]))
                    self.addToLog ("#  Should be sent:%s Delay:%s" % (c['c'], c['d']))
                
                r = c['r']
                if len (list(r.ReceivedDI.keys ())):
                    # update relevant values
                    for d in list(r.ReceivedDI.keys ()):
                        val = self.decu.getValue (d, False, r, rsp)  # allow execute commands with manuelSend
                        if d in list(self.dValue.keys ()):
                            if ':' in val:
                                self.dValue[d].set (val.split (':')[1])
                            else:
                                self.dValue[d].set (val)
                        if d in list(self.iValue.keys ()):
                            if len (self.decu.datas[d].List) or self.decu.datas[d].BytesASCII \
                                    or self.decu.datas[d].Scaled:
                                self.iValue[d].set (val)
                            else:
                                val = self.decu.getHex (d, False, r, rsp)
                                if val != mod_globals.none_val:
                                    val = '0x' + val
                                self.iValue[d].set (val)
                            self.iValueNeedUpdate[d] = False
                
                self.addToLog ('#Finish command execution')
                if not mod_globals.opt_exp:
                    self.addToLog ("#WARNING!!! NOT EXPERT MODE!!! Commands wasn't realy sent to ECU")
        
        # re-launch periodic requests
        if self.start:
             self.jid = self.root.after (self.updatePeriod, self.updateScreen)
             self.decu.rotaryRunAlloved.set()
        
        # request to update dInputs
        self.update_dInputs()
    
    def OnScreenChange(self, item):
        self.loadScreen (self.ScreensMenu[item])
    
    def resizeEvent(self, event):
        # filter first resize
        if self.firstResize:
            self.firstResize = False
            return
        # stop previous resize update query
        if self.jdsu is not None:
            self.root.after_cancel (self.jdsu)
        # make new resize update query
        if self.currentscreen is not None:
            self.jdsu = self.root.after (500, lambda: self.loadScreen (self.currentscreen))
    
    def saveDump(self):
        self.decu.saveDump ()
    
    def askDumpName(self):
        flist = []
        for root, dirs, files in os.walk ("./dumps"):
            for f in files:
                if self.decu.ecufname.split ('/')[-1][:-4] in f:
                    try:
                        uda = f.split ('_')[0]
                        fda = datetime.datetime.fromtimestamp (int (uda)).strftime ('%Y/%m/%d %H:%M:%S')
                        flist.append (fda + '\t#\t' + f)
                    except:
                        tkinter.messagebox.showinfo ("Wrong dump file", "Wrong file name " + f + " in ./dumps folder")
                        return ""
        #if len (flist) == 0:
        #    tkinter.messagebox.showinfo ("Wrong dump file", "No appropriate dump file in ./dumps folder")
        #    return ""
    
        ch = ListDialog (self.root, "Choose dump file", flist).show ()
    
        try:
            if "#" in ch:
                fname = './dumps/' + ch.split ("#")[1].strip ()
            elif os.path.isfile( ch ):
                fname = ch
            else:
                tkinter.messagebox.showinfo ("Wrong dump file", "Can't find a file")
                return ""
        except:
            tkinter.messagebox.showinfo ("Wrong dump file", "No appropriate dump file in ./dumps folder")
            return ""
        # check dump file
        #if self.decu.ecufname.split ('/')[-1][:-4] not in fname:
        #    tkinter.messagebox.showinfo ("Wrong dump file", "The name of dump file should contains the name of current xml.")
        #    return ""
    
        return fname
    
    def loadDump(self):
        fname = self.askDumpName()
        self.decu.loadDump (fname)

        # clear elm cache
        self.decu.clearELMcache ()

        # request to update dInputs
        self.update_dInputs ()


    def dumpRollBack(self):
    
        fname = self.askDumpName ()

        if fname == '':
            return

        # stop periodic requests
        if self.jid is not None:
            self.root.after_cancel (self.jid)
        self.decu.rotaryRunAlloved.clear()

        (conf_2, cv_2) = self.decu.makeConf()

        savedMode = mod_globals.opt_demo
        mod_globals.opt_demo = True
        saveDumpName = mod_globals.dumpName
        self.decu.loadDump (fname)

        (conf_1, cv_1) = self.decu.makeConf(indump=True)

        mod_globals.dumpName = saveDumpName
        mod_globals.opt_demo = savedMode
        if mod_globals.opt_demo:
            self.decu.loadDump(mod_globals.dumpName)
        else:
            self.decu.clearELMcache()


        diff = list(set(conf_1)-set(conf_2))
        
        # show confirmation dialog if approve is True
        confirmed = True
        xText = '\n\n'
        sendDelay = '1000'
        for i in diff:
            xText += "%-10s Delay:%s\n" % (i,sendDelay)
        confirmed = ButtonConfirmationDialog (self.root, xText).show ()
        
        # send commands
        if confirmed:
            self.addToLog ('#Starting command execution')
            for c in diff:
                rsp = '00'
        
                # protection for debug period
                if mod_globals.opt_exp:
                    rsp = self.decu.elmRequest (c, sendDelay, cache=False)
                else:
                    self.addToLog ("#  Should be sent:%s Delay:%s" % (c, sendDelay))
                
            self.addToLog ('#Finish command execution')
            if not mod_globals.opt_exp:
                self.addToLog ("#WARNING!!! NOT EXPERT MODE!!! Commands wasn't realy sent to ECU")

        # re-launch periodic requests
        if self.start:
            self.jid = self.root.after (self.updatePeriod, self.updateScreen)
            self.decu.rotaryRunAlloved.set()

        # request to update dInputs
        self.update_dInputs()
        del(conf_1)
        del(conf_2)
        del(cv_1)
        del(cv_2)

    def makeMacro(self):

        fname = self.askDumpName()

        if fname == '':
            return

        # stop periodic requests
        if self.jid is not None:
            self.root.after_cancel(self.jid)
        self.decu.rotaryRunAlloved.clear()

        #save state
        savedMode = mod_globals.opt_demo
        mod_globals.opt_demo = True
        saveDumpName = mod_globals.dumpName
        self.decu.loadDump(fname)

        (conf_1, cv_1) = self.decu.makeConf(indump=True, annotate=True)

        #restore state
        mod_globals.dumpName = saveDumpName
        mod_globals.opt_demo = savedMode
        if mod_globals.opt_demo:
            self.decu.loadDump(mod_globals.dumpName)
        else:
            self.decu.clearELMcache()

        # show confirmation dialog if approve is True
        confirmed = True
        xText = f'#The macro made by mod_ddt from file {fname}\n\n'
        if self.decu.cecu != None:
            xText += f'$addr = {self.decu.cecu["dst"]}\n\n'
            if self.decu.cecu["pin"] == 'can' and self.decu.cecu["brp"] == '0':
                xText += f'can500  # init can macro\n\n'
            elif self.decu.cecu["pin"] == 'can' and self.decu.cecu["brp"] == '1':
                xText += f'can250  # init can macro\n\n'
            else:
                xText += f'fast  # init iso macro\n\n'
            xText += f'delay 1\n\n'
            xText += f'# open session\n\n'
            xText += f'session {self.decu.cecu["startDiagReq"]}\n\n'
            xText += f'# configuration\n\n'

        for i in conf_1:
            xText += f'{i}\n'
        xText += f'\n'

        #find reset
        reset_command = ''
        for req in self.decu.requests.keys():
            if self.decu.requests[req].SentBytes == '1101':
                reset_command = req
                break
        if reset_command!='':
            xText += f'#Reset command: {req}\n'
            xText += f'#{self.decu.requests[req].SentBytes}\n\n'

        xText += f'exit\n'

        dialog = InfoDialog(self.root, xText, hnid=False)
        self.root.wait_window(dialog.top)

        # re-launch periodic requests
        if self.start:
            self.jid = self.root.after(self.updatePeriod, self.updateScreen)
            self.decu.rotaryRunAlloved.set()

        # request to update dInputs
        self.update_dInputs()
        del (conf_1)
        del (cv_1)

    def dumpName2str(self, dn):
        uda = dn.split('/')[-1].split('_')[0]
        fda = datetime.datetime.fromtimestamp(int(uda)).strftime('%Y/%m/%d %H:%M:%S')
        return fda + '\t#\t' + dn

    def showDiff(self):

        fname = self.askDumpName()

        if fname == '':
            return

        # stop periodic requests
        if self.jid is not None:
            self.root.after_cancel(self.jid)
        self.decu.rotaryRunAlloved.clear()
        
        (conf_2, cv_2_tmp) = self.decu.makeConf()

        cv_2 = copy.deepcopy(cv_2_tmp)

        #clear memory
        del (conf_2)
        del (cv_2_tmp)

        savedMode = mod_globals.opt_demo
        mod_globals.opt_demo = True
        saveDumpName = mod_globals.dumpName
        self.decu.loadDump(fname)
        
        (conf_1, cv_1_tmp) = self.decu.makeConf(indump = True)

        cv_1 = copy.deepcopy(cv_1_tmp)

        # clear memory
        del (conf_1)
        del (cv_1_tmp)

        du_1 = copy.deepcopy (self.decu.elm.ecudump)

        mod_globals.dumpName = saveDumpName
        mod_globals.opt_demo = savedMode
        if mod_globals.opt_demo:
            self.decu.loadDump(mod_globals.dumpName)
        else:
            self.decu.clearELMcache()

        #debug
        #print cv_2
        #print '#'*100
        #print cv_1
        #print '#'*100

        aK = list(set(cv_1) | set(cv_2))

        # show confirmation dialog if approve is True
        xText = '< ' + self.dumpName2str(fname) + '\n'
        if mod_globals.opt_demo:
            xText += '> ' + self.dumpName2str(mod_globals.dumpName) + '\n\n'
        else:
            xText += '> Current ECU state\n'

        #debug
        #print du_1

        flag = True
        for i in aK:
            if i in list(self.decu.req4data.keys ()):
                i_r_cmd = self.decu.requests[self.decu.req4data[i]].SentBytes
            else:
                continue

            #debug
            #print '>', i, i_r_cmd

            if (i not in list(cv_1.keys())) or (i not in list(cv_2.keys())) or cv_1[i]!=cv_2[i]:
                flag = False
                xText += ("-"*30+ "\n%s\n" % (i))

                if i in list(cv_1.keys()) and cv_1[i] != '':
                    xText += "< %s\n" % (cv_1[i])
                elif i_r_cmd not in list(du_1.keys()) or du_1[i_r_cmd]=='':
                    xText += "< None\n"
                else:
                    xText += "< ERROR\n"

                if i in list(cv_2.keys()) and cv_2[i] != '':
                    xText += "> %s\n" % (cv_2[i])
                else:
                    xText += "< ERROR\n"

        if flag:
            xText += "No difference \n"

        dialog = InfoDialog(self.root, xText, hnid=True )
        self.root.wait_window(dialog.top)

        # re-launch periodic requests
        if self.start:
            self.jid = self.root.after(self.updatePeriod, self.updateScreen)
            self.decu.rotaryRunAlloved.set()

        # request to update dInputs
        self.update_dInputs()
        del (cv_1)
        del (cv_2)
        del (du_1)

    def repaint(self):
        self.loadScreen (self.currentscreen)
    
    def changeMode(self):
        mod_globals.opt_exp = self.expertmode.get ()
        if mod_globals.opt_exp:
            self.modeLabel.configure (text="Expert Mode", background='#d9d9d9', foreground='#d90000')
        else:
            self.modeLabel.configure (text="ReadOnly Mode", background='#d9d9d9', foreground='#000000')
    
    def changeInpPref(self):
        if self.prefer_ECU.get ():
            self.inpPrefLabel.configure (text="Inputs derived from ECU", background='#d9d9d9', foreground='#000000')
        else:
            self.inpPrefLabel.configure (text="Inputs derived from XML", background='#d9d9d9', foreground='#000000')
            # request to update dInputs
        self.update_dInputs()
    
    def fontUp(self, event=None):
        self.scf = self.scf * 1.25
        self.loadScreen (self.currentscreen)
    
    def fontDown(self, event=None):
        self.scf = self.scf * 0.8
        self.loadScreen (self.currentscreen)
    
    def exit(self):

        # clean shut down
        
        if self.decu is not None:
            self.decu.rotaryRunAlloved.clear()
            self.decu.rotaryTerminate.set ()
    
        if self.jid is not None:
            self.root.after_cancel (self.jid)

        if self.jdsu is not None:
            self.root.after_cancel (self.jdsu)

        try:
            if self.translated is not None: del(self.translated)
        except:
            pass
        try:
            if self.expertmode is not None: del(self.expertmode)
        except:
            pass
        try:
            if self.approve is not None: del(self.approve)
        except:
            pass
        try:
            if self.prefer_ECU is not None: del(self.prefer_ECU)
        except:
            pass
        try:
            if self.Screens is not None: del(self.Screens)
        except:
            pass
        try:
            if self.ScreensMenu is not None: del(self.ScreensMenu)
        except:
            pass
        try:
            if self.dDisplay is not None: del(self.dDisplay)
        except:
            pass
        try:
            if self.dValue is not None: del(self.dValue)
        except:
            pass
        try:
            if self.iValue is not None: del(self.iValue)
        except:
            pass
        try:
            if self.iValueNeedUpdate is not None: del(self.iValueNeedUpdate)
        except:
            pass
        try:
            if self.dReq is not None: del(self.dReq)
        except:
            pass
        try:
            if self.sReq_dl is not None: del(self.sReq_dl)
        except:
            pass
        try:
            if self.sReq_lst is not None: del(self.sReq_lst)
        except:
            pass
        try:
            if self.dBtnSend is not None: del(self.dBtnSend)
        except:
            pass
        try:
            if self.dFrames is not None: del(self.dFrames)
        except:
            pass
        try:
            if self.dObj is not None: del(self.dObj)
        except:
            pass
        try:
            if self.tObj is not None: del(self.tObj)
        except:
            pass
        try:
            if self.images is not None: del(self.images)
        except:
            pass
        try:
            if self.root is not None: self.root.destroy ()
        except:
            pass

    def csv_save(self):
        # No screen selected so nothing to write
        if self.currentscreen == None or self.csv:
            self.csv = False
            if self.csv_file!=None:
                self.csv_file.close()
            self.csvButton.configure(text='CSV')
        else:
            #open new csv file
            csv_file_name = './csv/' \
                            + str(int(time.time()))+'_' \
                            + self.currentscreen.attrib['Name'].replace(' ','_') \
                            + '.csv'
            self.csv_file = open( csv_file_name, "wt")
            self.csv_file.write('sep=\\t\n')
            self.sortedValueKeys = sorted(self.dValue.keys())
            column_list = ['time'] + self.sortedValueKeys
            self.csv_file.write('\t'.join(column_list)+'\n')
            self.csvButton.configure(text='Pause')
            self.csv = True
            if os.path.isfile('./csv_monitor.py'):
                subprocess.Popen([sys.executable, './csv_monitor.py', csv_file_name])
        return
  
    def startStop(self):
        if self.start:
            # stop it
            self.start = False
            self.sessionmenu.entryconfig (0, label='Start')
            self.startStopButton.configure (text='Start')
            if self.jid is not None:
                self.root.after_cancel (self.jid)
            self.decu.rotaryRunAlloved.clear()
        else:
            # start it
            self.start = True
            self.sessionmenu.entryconfig (0, label='Stop')
            self.startStopButton.configure (text='Stop')
            self.jid = self.root.after (self.updatePeriod, self.updateScreen)
            self.decu.rotaryRunAlloved.set()
        return
    
    def addToLog(self, log):
        self.eculog.insert (tk.END, log + '\n')
        self.eculog.see (tk.END)
    
    def OnTreeClick(self, event):
        iid = self.tree.focus ()
        if iid in list(self.Screens.keys ()):
            self.loadScreen (self.Screens[iid])
    
    def ddtColor(self, s):
        si = int (s)
        if si < 0: si = si * -1 + 0x800000
        c = hex (si).replace ("0x", "").zfill (6).upper ()
        return '#' + c[4:6] + c[2:4] + c[0:2]
    
    def clearLogs(self):
        self.eculog.delete (1.0, tk.END)
    
    def saveLogs(self):
        fname = ''
        fname = tkinter.filedialog.asksaveasfilename (defaultextension=".txt",
                                                filetypes=[("Text files", ".txt")],
                                                initialdir="logs",
                                                title="Save as")
        if len (fname):
            with open (fname, "w") as log:
                log.write (self.eculog.get (1.0, tk.END))
    
    def readDTC(self):
        tkinter.messagebox.showinfo ("Read DTC", "Under construction. Use pyren screens.")
    
    def clearDTC(self):
        tkinter.messagebox.showinfo ("Clear DTC", "Under construction. Use pyren screens.")
    
    def rightButtonClicked(self, event, tag=''):
        id = self.ddt.find_closest (event.x, event.y)[0]
        
        if id not in list(self.tObj.keys ()) and tag == '': return
        
        if tag != '':
            closest = tag
        else:
            closest = self.tObj[self.ddt.find_closest (event.x, event.y)[0]]

        p = self.decu.getParamExtr(closest, self.iValue, self.dValue )
        
        d = str (self.decu.datas[closest])
        r = ''
        if closest in list(self.decu.req4data.keys ()) and \
                        self.decu.req4data[closest] in list(self.decu.requests.keys ()):
            r = str (self.decu.requests[self.decu.req4data[closest]])

        
        try:
            xText = d + '\n' + '*' * 50 + '\n'
        except:
            pass
        try:
            xText += r + '\n' + '*' * 50 + '\n'
        except:
            pass
        try:
            xText += p
        except:
            pass

        dialog = InfoDialog (self.root, xText)
        self.root.wait_window (dialog.top)
    
    def find(self):

        restart = False
        if self.start:
           self.startStop()
           restart = True

        scr_name = FindDialog(self.root, self.decu ).show()
        if '@' in scr_name:
            key = scr_name.split('@')[0]
            if key in self.Screens.keys() :
                #self.loadSyntheticScreen (self.Screens[key])
                #else:
                self.loadScreen (self.Screens[key])

        if restart:
           self.startStop()

        return

    def create_custome_screen_xml(self, screen_name: str, parameters: list, cust_update ) -> et.Element:

        NS_SCREENS = "http://www-diag.renault.com/2002/screens"

        et.register_namespace('xmlns', 'http://www-diag.renault.com/2002/screens')

        root = et.Element("xml", {
            "xmlns:ns1": "http://www-diag.renault.com/2002/screens"
        })

        # Generator
        generator = et.SubElement(root, "Generator", {
            "name": "DDT2000 XML library",
            "version": "2.2.0.0"
        })

        # Target
        target = et.SubElement(root, "{http://www-diag.renault.com/2002/screens}Target", {
            "xmlns": "http://www-diag.renault.com/2002/screens",
            "xmlns:ns1": "http://www-diag.renault.com/2002/screens"
        })

        # Screen
        screen = et.SubElement(target, f"{{{NS_SCREENS}}}Screen", {
            "Name": screen_name,
            "Color": "16777088",
            "WindowState": "0",
            "Width": "14000",
            "Height": "1200",
            "Update_gap_ms": cust_update
        })

        label_header = et.SubElement(screen, f"{{{NS_SCREENS}}}Label", {
            "Text": screen_name,
            "Color": "16744703",
            "Alignment": "2"
        })
        rect_header = et.SubElement(label_header, f"{{{NS_SCREENS}}}Rectangle", {
            "Left": "200",
            "Top": "50",
            "Height": "250",
            "Width": "13600"
        })
        font_header = et.SubElement(label_header, f"{{{NS_SCREENS}}}Font", {
            "Name": "Ms Sans Serif",
            "Size": " 8",
            "Bold": "0",
            "Italic": "0",
            "Color": "0"
        })

        top_offset = 400 
        for param in parameters:
            label = et.SubElement(screen, f"{{{NS_SCREENS}}}Label", {
                "Text": param,
                "Color": "8454143",
                "Alignment": "0"
            })
            rect_label = et.SubElement(label, f"{{{NS_SCREENS}}}Rectangle", {
                "Left": "200",
                "Top": str(top_offset),
                "Height": "250",
                "Width": "6700"
            })
            font_label = et.SubElement(label, f"{{{NS_SCREENS}}}Font", {
                "Name": "Ms Sans Serif",
                "Size": " 8",
                "Bold": "0",
                "Italic": "0",
                "Color": "0"
            })

            display = et.SubElement(screen, f"{{{NS_SCREENS}}}Display", {
                "Width": "0",
                "Color": "8454143",
                "DataName": param,
                "RequestName": self.decu.req4data[param]
            })
            rect_display = et.SubElement(display, f"{{{NS_SCREENS}}}Rectangle", {
                "Left": "7100",
                "Top": str(top_offset),
                "Height": "250",
                "Width": "6700"
            })
            font_display = et.SubElement(display, f"{{{NS_SCREENS}}}Font", {
                "Name": "Ms Sans Serif",
                "Size": " 8",
                "Bold": "0",
                "Italic": "0",
                "Color": "0"
            })

            top_offset += 300

        return root 

    def loadCustomScreen(self):

        restart = False
        if self.start:
           self.startStop()
           restart = True

        fname = ''
        fname = tkinter.filedialog.askopenfilename( defaultextension=".txt",
                                                filetypes=[("TXT files", ".txt")],
                                                initialdir=".",
                                                title="file with list of parameters")
        
        if len(fname):
            fprm = open(fname,'rt')
        else:
            return
        
        lprm = fprm.read()
        lprm = re.split(r'[ \t\n,;]+', lprm)
        lprm = [prm.strip() for prm in lprm if prm.strip() in self.decu.datas.keys()]
        act_prm = []
        cust_update = self.updatePeriod
        for prm in lprm:
            prm = prm.strip()
            if prm.startswith('#'):
                if 'update:' in prm:
                    match = re.search(r'^#[ \t]*update[ \t]*:[ \t]*(\d+)', prm)  # Находим последовательность цифр после '#update:'
                    if match:
                        cust_update = int(match.group(1))
                continue
            if prm in self.decu.datas.keys():
                act_prm.append(prm)
        
        cst_name = Path(fname).stem
        cst_xml = self.create_custome_screen_xml(cst_name, act_prm, cust_update )
        #xml_str = et.tostring(cst_scr, encoding="unicode",)
        #print(xml_str)

        ns = {'ns0': 'http://www-diag.renault.com/2002/ECU',
              'ns1': 'http://www-diag.renault.com/2002/screens'}
        
        cst_scr = cst_xml.find(".//ns1:Screen", ns)

        iid = self.tree.insert('custom_screens', "end", text=cst_name)
        self.Screens[iid] = cst_scr

        self.loadScreen (self.Screens[iid])

        if restart:
           self.startStop()

        return

    def torqpids(self):
        fname = ''
        fname = tkinter.filedialog.asksaveasfilename (defaultextension=".csv",
                                                filetypes=[("CSV files", ".csv")],
                                                initialdir=".",
                                                title="Save as")
        
        if len (fname):
            fcsv = open(fname, "w")
            fcsv.write ("name,ShortName,ModeAndPID,Equation,Min Value,Max Value,Units,Header\n")
        else:
            return

        if self.decu.elm.currentprotocol=='can':
            l_header = dnat[self.decu.elm.currentaddress]
        else:
            l_header = '82'+self.decu.elm.currentaddress+'F1'
            
        usedmnemo = []
        for dk in list(self.decu.datas.keys ()):
            if dk in list(self.decu.req4data.keys()):
                if self.decu.req4data[dk] in list(self.decu.requests.keys ()):
                    rk = self.decu.req4data[dk]
                    r = self.decu.requests[rk]
                    d = self.decu.datas[dk]

                    l_Endian = r.ReceivedDI[dk].Endian
                    l_FirstByte = r.ReceivedDI[dk].FirstByte
                    l_BitOffset = r.ReceivedDI[dk].BitOffset
                    l_SentBytes = r.SentBytes
                    if d.Scaled or d.BitsCount==1:
                        l_Mnemonic = d.Mnemonic
                        l_BytesCount = d.BytesCount
                        l_signed = d.signed
                        l_Step = d.Step
                        l_Offset = d.Offset
                        l_DivideBy = d.DivideBy
                        l_Unit = d.Unit
                        
                        if l_Mnemonic in usedmnemo:
                            l_Mnemonic = dk
                        else:
                            usedmnemo.append( l_Mnemonic )
                        
                        equ = self.decu.get_ddt_pid( d.Scaled, d.BitsCount, l_Endian, l_FirstByte, l_BitOffset,
                                     l_signed, l_Step, l_Offset, l_DivideBy, l_SentBytes)
                        cs = '"'
                        cs = cs + self.decu.translate(dk) + '","'
                        cs = cs + l_Mnemonic + '","'
                        cs = cs + l_SentBytes + '","'
                        cs = cs + equ + '","0","0","'
                        cs = cs + l_Unit + '","'
                        cs = cs + l_header + '"\n'

                        fcsv.write(cs)
        fcsv.close()
        del(usedmnemo)

    def initUI(self):
    
        ns = {'ns0': 'http://www-diag.renault.com/2002/ECU',
              'ns1': 'http://www-diag.renault.com/2002/screens'}
    
        if mod_globals.os == 'nt':
            self.scf = 1.0  # scale font
        else:
            self.scf = 1.25  # scale font

        screenTitle = self.xmlName
        if mod_globals.opt_demo:
            screenTitle = 'OFF-LINE: ' + screenTitle

        self.root.title (screenTitle)
        self.style = tkinter.ttk.Style ()
        self.style.theme_use ('classic')
        
        self.screen_width = self.root.winfo_screenwidth ()
        self.screen_height = self.root.winfo_screenheight ()
        
        bot_h = 50 if self.screen_height > 850 else 20
        lef_w = 200 if self.screen_width > 1000 else 0
        
        # print self.screen_width, self.screen_height
        
        # create main layout
        self.tbpw = tk.PanedWindow (self.root, orient=tk.VERTICAL, background='#d9d9d9'
                                    , handlepad=0, sashpad=0, sashrelief=tk.GROOVE, showhandle=1)
        # top farme (Main Screen)
        self.top_f = tk.Frame (self.tbpw, background='#d9d9d9')
        
        # bottom farme (Ecu Log)
        self.bot_f = tk.Frame (self.tbpw, background='#d9d9d9')
        self.eculog = tk.Text (self.bot_f, relief=tk.GROOVE, borderwidth=1, height=4)
        self.eculog.pack (fill=tk.BOTH, expand=True)
        
        self.tbpw.add (self.top_f, height=748)
        self.tbpw.add (self.bot_f, height=bot_h)
        
        self.tbpw.pack (fill=tk.BOTH, expand=True)
        self.root.update ()
        
        # create menu
        self.menubar = tk.Menu (self.root)
        
        self.sessionmenu = tk.Menu (self.menubar, tearoff=0)
        self.sessionmenu.add_command (label="Stop", command=self.startStop)
        self.sessionmenu.add_command (label="Exit", command=self.exit)
        self.menubar.add_cascade (label="Session", menu=self.sessionmenu)
        
        self.viewmenu = tk.Menu (self.menubar, tearoff=0)
        self.viewmenu.add_command (label="Font Increse  (+)", command=self.fontUp)
        self.viewmenu.add_command (label="Font Decrease (_)", command=self.fontDown)
        self.menubar.add_cascade (label="View", menu=self.viewmenu)
        
        self.toolsmenu = tk.Menu (self.menubar, tearoff=0)
        self.toolsmenu.add_command (label="Make torque PIDs", command=self.torqpids, accelerator="Ctrl+t")
        self.toolsmenu.add_command (label="Load custom screen", command=self.loadCustomScreen )
        self.toolsmenu.add_command (label="Find", command=self.find, accelerator="Ctrl+f")
        self.toolsmenu.add_command (label="Clear logs", command=self.clearLogs, accelerator="Ctrl+k")
        self.toolsmenu.add_command (label="Save logs to file", command=self.saveLogs, accelerator="Ctrl+s")
        self.menubar.add_cascade (label="Tools", menu=self.toolsmenu)
        
        #self.DTCmenu = tk.Menu (self.menubar, tearoff=0)
        #self.DTCmenu.add_command (label="Read DTC", command=self.readDTC)
        #self.DTCmenu.add_command (label="Clear DTC", command=self.clearDTC)
        #self.menubar.add_cascade (label="DTC", menu=self.DTCmenu)
        
        self.toolmenu = tk.Menu (self.menubar, tearoff=0)
        self.toolmenu.add_command (label="RollBack", command=self.dumpRollBack)
        self.toolmenu.add_separator ()
        self.toolmenu.add_command (label="Make macro from dump", command=self.makeMacro)
        self.toolmenu.add_separator ()
        self.toolmenu.add_command (label="Show diff", command=self.showDiff)
        self.toolmenu.add_separator ()
        if mod_globals.opt_demo:
            self.toolmenu.add_command (label="Load DUMP", command=self.loadDump)
        else:
            self.toolmenu.add_command (label="Save DUMP", command=self.saveDump)
        self.menubar.add_cascade (label="Dumps", menu=self.toolmenu)
        
        self.settingsmenu = tk.Menu (self.menubar, tearoff=0)
        self.settingsmenu.add_separator ()
        self.settingsmenu.add_checkbutton (label="Translate", onvalue=True, offvalue=False, variable=self.translated,
                                           command=self.repaint)
        self.settingsmenu.add_separator ()
        self.settingsmenu.add_checkbutton (label="Prefer Inputs from ECU", onvalue=True, offvalue=False,
                                           variable=self.prefer_ECU, command=self.changeInpPref)
        self.settingsmenu.add_separator ()
        self.settingsmenu.add_checkbutton (label="Approve commands", onvalue=True, offvalue=False,
                                           variable=self.approve)
        self.settingsmenu.add_separator ()
        self.settingsmenu.add_separator ()
        self.settingsmenu.add_checkbutton (label="Expert Mode ( be careful !!! )", onvalue=True, offvalue=False,
                                           variable=self.expertmode, command=self.changeMode)
        self.menubar.add_cascade (label="Settings", menu=self.settingsmenu)
        
        self.ecumenu = tk.Menu (self.menubar, tearoff=0)
        
        categs = self.xdoc.findall ("ns0:Target/ns1:Categories/ns1:Category", ns)
        if len(categs):
            for cat in categs:
                catname = cat.attrib["Name"]
                catmenu = tk.Menu (self.ecumenu, tearoff=0)
                self.ecumenu.add_cascade (label=catname, menu=catmenu)
                screens = cat.findall ("ns1:Screen", ns)
                if len(screens):
                    for scr in screens:
                        scrname = scr.attrib["Name"]
                        self.ScreensMenu[scrname] = scr
                        catmenu.add_command (label=scrname, command=lambda item=scrname: self.OnScreenChange (item))
        self.menubar.add_cascade (label="Screens", menu=self.ecumenu)
        self.root.config (menu=self.menubar)
        
        self.lrpw = tk.PanedWindow (self.top_f, orient=tk.HORIZONTAL, background='#d9d9d9'
                                    , handlepad=0, sashpad=0, sashrelief=tk.GROOVE, showhandle=1)
        # left farme
        self.lef_f = tk.Frame (self.lrpw, background='#d9d9d9')
        # right farme
        self.rig_f = tk.Frame (self.lrpw, background='#d9d9d9')
        self.lrpw.add (self.lef_f, width=lef_w)
        self.lrpw.add (self.rig_f, width=800)
        self.lrpw.pack (fill=tk.BOTH, expand=True)
        self.root.update ()
        
        if mod_globals.opt_exp:
            self.modeLabel = tk.Label (self.lef_f, height=1, text="Expert Mode", background='#d9d9d9',
                                       foreground='#d90000')
        else:
            self.modeLabel = tk.Label (self.lef_f, height=1, text="ReadOnly Mode", background='#d9d9d9',
                                       foreground='#000000')
        self.modeLabel.pack (side=tk.TOP)
        
        if self.prefer_ECU.get ():
            self.inpPrefLabel = tk.Label (self.lef_f, height=1, text="Inputs derived from ECU", background='#d9d9d9',
                                          foreground='#000000')
        else:
            self.inpPrefLabel = tk.Label (self.lef_f, height=1, text="Inputs derived from XML", background='#d9d9d9',
                                          foreground='#000000')
        self.inpPrefLabel.pack (side=tk.TOP)
        
        btnFrame = tk.Frame (self.lef_f, background='#d9d9d9')
        btnFrame.pack (side=tk.TOP, fill=tk.X)
        self.exitButton = tkinter.ttk.Button (btnFrame, text="Exit", command=self.exit)
        self.exitButton.pack (side=tk.RIGHT, expand=True)
        self.csvButton = tkinter.ttk.Button (btnFrame, text="CSV", command=self.csv_save)
        self.csvButton.pack (side=tk.LEFT, expand=True)
        self.startStopButton = tkinter.ttk.Button (btnFrame, text="Stop", command=self.startStop)
        self.startStopButton.pack (side=tk.LEFT, expand=True)
        
        # add treeView on left frame
        self.tree = tkinter.ttk.Treeview (self.lef_f)
        self.tree.heading ('#0', text='Screens', anchor='w')
        categs = self.xdoc.findall ("ns0:Target/ns1:Categories/ns1:Category", ns)
        if len(categs):
            for cat in categs:
                catname = cat.attrib["Name"]
                self.tree.insert ("", "end", catname, text=catname, open=True)
                screens = cat.findall ("ns1:Screen", ns)
                if len(screens):
                    for scr in screens:
                        scrname = scr.attrib["Name"]
                        iid = self.tree.insert (catname, "end", text=scrname)
                        self.Screens[iid] = scr

        # commands tree
        self.tree.insert("", "end", 'ddt_all_commands', text='ddt_all_commands', open=False)
        for req in sorted(self.decu.requests.keys()):
            if self.decu.requests[req].SentBytes[:2] in ['21','22']:
                iid = self.tree.insert('ddt_all_commands', "end", text=req)
                self.Screens[iid] = req

        self.tree.insert("", "end", 'custom_screens', text='custom_screens', open=True)

        self.tree.bind ("<<TreeviewSelect>>", self.OnTreeClick)
        self.tree.pack (side=tk.BOTTOM, fill=tk.BOTH, expand=True)
        
        ######################################################################################
        
        # self.ddt = tk.Canvas(self.rig_f, relief=tk.GROOVE, width = 600, height = 500)
        
        ######################################################################################
        
        # Mad way to do scrollable convas
        
        self.ddtcnv = tk.Canvas (self.rig_f, relief=tk.GROOVE, width=600, height=600)
        self.vbar = tk.Scrollbar (self.rig_f, orient=tk.VERTICAL, command=self.ddtcnv.yview)
        self.ddtcnv.config (yscrollcommand=self.vbar.set)
        
        self.vbar.pack (side=tk.RIGHT, fill=tk.Y)
        self.ddtcnv.pack (side=tk.LEFT, expand=True, fill=tk.BOTH)
        
        self.ddtcnv.xview_moveto (0)
        self.ddtcnv.yview_moveto (0)
        
        self.ddtfrm = tk.Frame (self.ddtcnv, width=600, height=600)
        self.ddtfrm_id = self.ddtcnv.create_window ((0, 0), window=self.ddtfrm, anchor=tk.NW)
        # self.ddtfrm.pack(expand=True,fill=tk.BOTH)
        
        self.ddt = tk.Canvas (self.ddtfrm, relief=tk.GROOVE, width=600, height=600)
        self.ddt.pack (expand=True, fill=tk.BOTH)
        
        ######################################################################################
        
        #if os.name == 'posix':
        #    self.ddt.bind ("<Button-2>", self.rightButtonClicked)
        #else:
        #    self.ddt.bind ("<Button-3>", self.rightButtonClicked)
        self.ddt.event_add('<<RightClick>>', '<Button-2>', '<Button-3>')
        self.ddt.bind('<<RightClick>>', self.rightButtonClicked)

        # self.ddt.pack(fill=tk.BOTH, expand=True)
        self.ddtfrm.bind ("<Configure>", self.confFrm)
        self.ddtcnv.bind ("<Configure>", self.confDdt)
        
        self.rig_f.bind ("<Configure>", self.resizeEvent)
    
    def confFrm(self, event):
        size = (self.ddtfrm.winfo_reqwidth (), self.ddtfrm.winfo_reqheight ())
        self.ddtcnv.config (scrollregion="0 0 %s %s" % size)
        if self.ddtfrm.winfo_reqwidth () != self.ddtcnv.winfo_width ():
            self.ddtcnv.config (width=self.ddtfrm.winfo_reqwidth ())
    
    def confDdt(self, event):
        if self.ddtfrm.winfo_reqwidth () != self.ddtcnv.winfo_width ():
            self.ddtcnv.itemconfigure (self.ddtfrm_id, width=self.ddtcnv.winfo_width ())
    
    def minInputHeight(self, scr):
    
        ns = {'ns0': 'http://www-diag.renault.com/2002/ECU',
              'ns1': 'http://www-diag.renault.com/2002/screens'}
    
        _minInputHeight = 0xffff
        inputs = scr.findall ("ns1:Input", ns)
        if len(inputs):
            for input in inputs:
                xRect = input.findall ("ns1:Rectangle", ns)[0]
                if len(xRect):
                    xrHeight = int (xRect.attrib["Height"])
                    if xrHeight < _minInputHeight:
                        _minInputHeight = xrHeight
        return _minInputHeight
    
    def minButtonHeight(self, scr):

        ns = {'ns0': 'http://www-diag.renault.com/2002/ECU',
              'ns1': 'http://www-diag.renault.com/2002/screens'}
    
        _minButtonHeight = 0xffff
        inputs = scr.findall ("ns1:Button", ns)
        if len(inputs):
            for input in inputs:
                xRect = input.findall ("ns1:Rectangle", ns)[0]
                if len(xRect):
                    xrHeight = int (xRect.attrib["Height"])
                    if xrHeight < _minButtonHeight:
                        _minButtonHeight = xrHeight
        return _minButtonHeight
    
    def loadScreen(self, scr):

        # reset Expert mode with every screen changing
        mod_globals.opt_exp = False
        self.expertmode.set(False)
        self.changeMode()

        # stop csv writing by defining self.currentscreen = None
        self.sortedValueKeys = []
        self.csvValues = {}
        self.currentscreen = None
        self.csv_save()

        # new currentscreen
        self.currentscreen = scr

        # check if it synthetic screen
        if type(scr) is str or type(scr) is str:
            self.loadSyntheticScreen(scr)
            return

        #debug
        #deb_time1 = pyren_time()
        #print( "#"*50 )

        # stop ratary. Do not read ELM
        restart = False
        if self.start:
           self.startStop()
           restart = True

        #debug
        #print( f"DEBUG POINT1: {pyren_time()-deb_time1}")

        ns = {'ns0': 'http://www-diag.renault.com/2002/ECU',
              'ns1': 'http://www-diag.renault.com/2002/screens'}

        self.firstResize = True
        
        scr_w = int (scr.attrib["Width"])
        scr_h = int (scr.attrib["Height"])
        bg_color = scr.attrib["Color"]
        if 'Update_gap_ms' in scr.attrib.keys():
            self.updatePeriod = scr.attrib["Update_gap_ms"]
        
        scx = 1  # scale X
        scy = 1  # scale Y
        
        # access scale
        max_x = 0.0
        max_y = 0.0
        recs = scr.findall ("*/ns1:Rectangle", ns)
        for rec in recs:
            xrLeft = int (rec.attrib["Left"])
            xrTop = int (rec.attrib["Top"])
            xrHeight = int (rec.attrib["Height"])
            xrWidth = int (rec.attrib["Width"])
            w = xrLeft + xrWidth
            h = xrTop + xrHeight
            if w > max_x and w < scr_w * 3:
                max_x = w
            if h > max_y and h < scr_h * 3:
                max_y = h
                # print xrLeft, xrTop, xrHeight, xrWidth
        
        # main frame re-create
        self.ddt.delete ('all')
        self.ddt.update_idletasks ()

        for o in self.dObj:
            o.destroy() # place_forget ()
        for f in self.dFrames:
            f.destroy() # place_forget ()
        
        self.dValue = {}  # value indexed by DataName
        self.iValue = {}  # value indexed by DataName param with choise
        self.iValueNeedUpdate = {}
        self.dReq = {}  # request names
        self.sReq_dl = {}  # delays for requests sent thru starting the screen
        self.sReq_lst = []  # list of requests sent thru starting the screen (order is important)
        self.dDisplay = {}  # displays object for renew
        self.dObj = []  # objects for place_forget
        self.tObj = {}  # objects for text captions
        self.dFrames = []  # container frames
        self.images = []  # images
        
        scx = int (max_x / self.ddtcnv.winfo_width () + 1)
        scy = int (max_y / self.ddtcnv.winfo_height () + 1)
        
        if scy < 10: scy = 10
        if scx < 10: scx = 10
        
        # print '*'*50
        # print 'max:',max_x,max_y, ' winfo:', self.ddtcnv.winfo_width(), self.ddtcnv.winfo_height()
        
        _minInputHeight = int (self.minInputHeight (scr)) // 25
        _minButtonHeight = int (self.minButtonHeight (scr)) // 25
        
        if _minInputHeight == 0: _minInputHeight = 10
        if _minButtonHeight == 0: _minButtonHeight = 20
        
        scx = min ([scx, 20])
        scy = min ([scy, _minInputHeight, _minButtonHeight, 10])

        # set scroll region
        self.ddtcnv.config (scrollregion=(0, 0, max_x // scx, max_y // scy))
        # self.ddtfrm.config(width=max_x/scx, height=max_y/scy)
        self.ddt.config (width=max_x // scx, height=max_y // scy, bg=self.ddtColor (bg_color))
        self.ddtcnv.xview_moveto (0)
        self.ddtcnv.yview_moveto (0)
        
        # load labels (just descriptions of fields)
        labels = scr.findall ("ns1:Label", ns)
        if len(labels):
            slab = []
            for label in labels:
    
                xRect_ = label.findall ("ns1:Rectangle", ns)
                if len(xRect_):
                    xRect = xRect_[0]
                    xrHeight = int (xRect.attrib["Height"]) // scy
                    xrWidth = int (xRect.attrib["Width"]) // scx
                else:
                    xrHeight = 1
                    xrWidth = 1
                sq = xrHeight * xrWidth
                sl = {}
                sl['sq'] = sq
                sl['lb'] = label
                slab.append (sl)
            
            for lab in sorted (slab, key=lambda k: k['sq'], reverse=True):
                label = lab['lb']
                xText = label.attrib["Text"]
                xColor = label.attrib["Color"]
                xAlignment = label.attrib["Alignment"]
                
                xRect = label.findall ("ns1:Rectangle", ns)
                if len(xRect):
                    xRect = xRect[0]
                    xrLeft = int (xRect.attrib["Left"]) // scx
                    xrTop = int (xRect.attrib["Top"]) // scy
                    xrHeight = int (xRect.attrib["Height"]) // scy
                    xrWidth = int (xRect.attrib["Width"]) // scx
                
                xFont = label.findall ("ns1:Font", ns)
                if len(xFont):
                    xFont = xFont[0]
                    # xfName    = xFont.attrib["Name")
                    # xfSize    = xFont.attrib["Size")
                    xfName = "Arial"
                    xfSize = "10"
                    xfBold = xFont.attrib["Bold"]
                    xfItalic = xFont.attrib["Italic"]
                    xfColor = xFont.attrib["Color"]
                
                if '::pic:' not in xText or not mod_db_manager.path_in_ddt('graphics'):
                    self.ddt.create_rectangle (xrLeft, xrTop, xrLeft + xrWidth, xrTop + xrHeight,
                                               fill=self.ddtColor (xColor), outline=self.ddtColor (xColor))
                
                if '::pic:' in xText:
                    self.ddt.create_rectangle (xrLeft, xrTop, xrLeft + xrWidth, xrTop + xrHeight,
                                               fill=self.ddtColor (65535), outline=self.ddtColor (0))

                if xText == 'New label': continue
                if xColor == xfColor: continue
                
                xfSize = str (int (float (xfSize) * self.scf))
                
                if xrLeft < 0: xrLeft = 0
                if xrTop < 0: xrTop = 0
                
                xfBold = 'bold' if xfBold == '1' else 'normal'
                xfItalic = 'italic' if xfItalic == '1' else 'roman'
                
                # if xAlignment=='0': continue
                
                if xAlignment == '1':
                    xrTop = xrTop + xrHeight // 2
                    xAlignment = 'w'
                elif xAlignment == '2':
                    xrLeft = xrLeft + xrWidth // 2
                    xAlignment = 'n'
                else:
                    xAlignment = 'nw'
                
                if '::pic:' not in xText:
                    lFont = tkinter.font.Font (family=xfName, size=xfSize, weight=xfBold)
                    id = self.ddt.create_text (xrLeft, xrTop, text=xText, font=lFont, width=xrWidth, anchor=xAlignment,
                                               fill=self.ddtColor (xfColor))
                else:
                    gifname = xText.replace ('::pic:', 'graphics/') + '.gif'
                    gifname = gifname.replace ('\\', '/')
                    gifname = mod_db_manager.extract_from_ddt_to_cache(gifname)
                    if gifname:
                        self.images.append (tk.PhotoImage (file=gifname))
                        x1 = self.images[-1].width ()
                        y1 = self.images[-1].height ()
                        self.images[-1] = self.images[-1].zoom (3, 3)
                        self.images[-1] = self.images[-1].subsample (x1 * 3 // xrWidth, y1 * 3 // xrHeight)
                        idg = self.ddt.create_image (xrLeft, xrTop, image=self.images[-1], anchor='nw')

        # load displays (show values)
        dispalys = scr.findall ("ns1:Display", ns)
        if len(dispalys):
            for dispaly in dispalys:
                xAlignment = '0'
                xText = ""
                if "DataName" in list(dispaly.attrib.keys()):
                  xText = dispaly.attrib["DataName"]
                xReq = ""
                if "RequestName" in list(dispaly.attrib.keys()):
                  xReq = dispaly.attrib["RequestName"]
                self.dReq[xReq] = self.decu.requests[xReq].ManuelSend
                xColor = ""
                if "Color" in list(dispaly.attrib.keys ()):
                  xColor = dispaly.attrib["Color"]
                xWidth = ""
                if "Width" in list(dispaly.attrib.keys ()):
                  xWidth = int (dispaly.attrib["Width"]) // scx
                
                xRect = dispaly.findall ("ns1:Rectangle", ns)
                if len(xRect):
                    xRect = xRect[0]
                    xrLeft = int (xRect.attrib["Left"]) // scx
                    xrTop = int (xRect.attrib["Top"]) // scy
                    xrHeight = int (xRect.attrib["Height"]) // scy
                    xrWidth = int (xRect.attrib["Width"]) // scx
                
                xFont = dispaly.findall ("ns1:Font", ns)
                if len(xFont):
                    xFont = xFont[0]
                    # xfName    = xFont.attrib["Name")
                    # xfSize    = xFont.attrib["Size")
                    xfName = "Arial"
                    xfSize = "10"
                    xfBold = xFont.attrib["Bold"]
                    xfItalic = xFont.attrib["Italic"]
                    xfColor = xFont.attrib["Color"]
                
                if len (xText) == 0:
                    if len (self.decu.requests[xReq].ReceivedDI) == 1:
                        xText = list(self.decu.requests[xReq].ReceivedDI.keys ())[0]
                    else:
                        xText = xReq
                
                self.dDisplay[xText] = 1
                
                self.ddt.create_rectangle (xrLeft, xrTop, xrLeft + xrWidth, xrTop + xrHeight,
                                           fill=self.ddtColor (xColor), outline=self.ddtColor (xColor))
                
                if xColor == xfColor: continue
                
                xfSize = str (int (float (xfSize) * self.scf))
                
                if xrLeft < 0: xrLeft = 0
                if xrTop < 0: xrTop = 0
                
                xfBold = 'bold' if xfBold == '1' else 'normal'
                xfItalic = 'italic' if xfItalic == '1' else 'roman'
                
                if xAlignment == '1':
                    xAlignment = 'w'
                elif xAlignment == '2':
                    xrLeft = xrLeft + xrWidth // 2
                    xAlignment = 'center'
                else:
                    xAlignment = 'w'
                
                lFont = tkinter.font.Font (family=xfName, size=xfSize, weight=xfBold)
                
                if xWidth > 40:
                    if self.translated.get ():
                        tText = self.decu.translate (xText)
                    else:
                        tText = xText
                    id = self.ddt.create_text (xrLeft, xrTop + xrHeight // 2, text=tText, font=lFont, width=xrWidth,
                                               anchor=xAlignment, fill=self.ddtColor (xfColor))
                    self.tObj[id] = xText
                
                frame = tk.Frame (self.ddt, width=xrWidth - xWidth, height=xrHeight, relief=tk.GROOVE, borderwidth=0)
                
                frame.place (x=xrLeft + xWidth, y=xrTop)
                self.dFrames.append (frame)
                
                if xText not in list(self.dValue.keys ()):
                    self.dValue[xText] = tk.StringVar ()
                    self.dValue[xText].set (mod_globals.none_val)
                
                obj = tk.Label (frame, text=self.dValue[xText], relief=tk.GROOVE, borderwidth=1, font=lFont,
                                textvariable=self.dValue[xText])
                
                obj.bind ('<<RightClick>>', lambda event, tag=xText: self.rightButtonClicked (event, tag))
                
                obj.place (width=xrWidth - xWidth, height=xrHeight)
                self.dObj.append (obj)
        
        # load Inputs (permits enter or choose values)
        inputs = scr.findall ("ns1:Input", ns)
        if len(inputs):
            for input in inputs:
                xAlignment = '0'
                xText = input.attrib["DataName"]
                xReq = input.attrib["RequestName"]
                xColor = input.attrib["Color"]
                xWidth = int (input.attrib["Width"]) // scx
                
                xRect = input.findall ("ns1:Rectangle", ns)
                if len(xRect):
                    xRect = xRect[0]
                    xrLeft = int (xRect.attrib["Left"]) // scx
                    xrTop = int (xRect.attrib["Top"]) // scy
                    xrHeight = int (xRect.attrib["Height"]) // scy
                    xrWidth = int (xRect.attrib["Width"]) // scx
                
                xFont = input.findall ("ns1:Font", ns)
                if len(xFont):
                    xFont = xFont[0]
                    xfName = xFont.attrib["Name"]
                    xfSize = xFont.attrib["Size"]
                    xfBold = xFont.attrib["Bold"]
                    xfItalic = xFont.attrib["Italic"]
                    xfColor = xFont.attrib["Color"]
                
                self.ddt.create_rectangle (xrLeft, xrTop, xrLeft + xrWidth, xrTop + xrHeight,
                                           fill=self.ddtColor (xColor), outline=self.ddtColor (xColor))
                
                if xColor == xfColor: continue
                
                xfSize = str (int (float (xfSize) * self.scf))
                
                if xrLeft < 0: xrLeft = 0
                if xrTop < 0: xrTop = 0
                
                xfBold = 'bold' if xfBold == '1' else 'normal'
                xfItalic = 'italic' if xfItalic == '1' else 'roman'
                
                if xAlignment == '1':
                    xrTop = xrTop + xrHeight // 2
                    xAlignment = 'w'
                elif xAlignment == '2':
                    xrTop = xrTop + xrHeight // 2
                    xrLeft = xrLeft + xrWidth // 2
                    xAlignment = 'center'
                else:
                    xAlignment = 'w'
                
                lFont = tkinter.font.Font (family=xfName, size=xfSize, weight=xfBold)
                if xWidth > 40:
                    if self.translated.get ():
                        tText = self.decu.translate (xText)
                    else:
                        tText = xText
                    id = self.ddt.create_text (xrLeft, xrTop + xrHeight / 2, text=tText, font=lFont, width=xrWidth,
                                               anchor=xAlignment, fill=self.ddtColor (xfColor))
                    self.tObj[id] = xText
                
                frame = tk.Frame (self.ddt, width=xrWidth - xWidth, height=xrHeight, relief=tk.GROOVE, borderwidth=0)
                
                frame.place (x=xrLeft + xWidth, y=xrTop)
                self.dFrames.append (frame)
                
                if xText not in list(self.iValue.keys ()):
                    if xText not in list(self.dValue.keys ()):
                        self.dValue[xText] = tk.StringVar ()
                    if xText in list(self.decu.req4data.keys ()) and self.decu.req4data[xText] in list(self.decu.requests.keys ()):
                        self.dReq[self.decu.req4data[xText]] = self.decu.requests[self.decu.req4data[xText]].ManuelSend
                    self.iValue[xText] = tk.StringVar ()
                    self.iValueNeedUpdate[xText] = True

                if xText in list(self.decu.datas.keys ()) and len (list(self.decu.datas[xText].List.keys ())):
                    optionList = []
                    if xText not in list(self.iValue.keys ()):
                        self.iValue[xText] = tk.StringVar ()
                        self.iValueNeedUpdate[xText] = True
                    for i in list(self.decu.datas[xText].List.keys ()):
                        optionList.append (
                            hex (int (i)).replace ("0x", "").upper () + ':' + self.decu.datas[xText].List[i])
                    self.iValue[xText].set (optionList[0])
                    obj = tk.OptionMenu (frame, self.iValue[xText], *optionList)
                else:
                    self.iValue[xText].set ('Enter here')
                    obj = tk.Entry (frame, relief=tk.GROOVE, borderwidth=1, font=lFont, textvariable=self.iValue[xText])
                
                obj.bind ('<<RightClick>>', lambda event, tag=xText: self.rightButtonClicked (event, tag))
                
                obj.place (width=xrWidth - xWidth, height=xrHeight)
                self.dObj.append (obj)
        
        # load buttons
        buttons = scr.findall ("ns1:Button", ns)
        if len(buttons):
            for button in buttons:
                xText = button.attrib["Text"]
                
                xRect = button.findall ("ns1:Rectangle", ns)
                if len(xRect):
                    xRect = xRect[0]
                    xrLeft = int (xRect.attrib["Left"]) // scx
                    xrTop = int (xRect.attrib["Top"]) // scy
                    xrHeight = int (xRect.attrib["Height"]) // scy
                    xrWidth = int (xRect.attrib["Width"]) // scx
                
                xFont = button.findall ("ns1:Font", ns)
                if len(xFont):
                    xFont = xFont[0]
                    xfName = xFont.attrib["Name"]
                    xfSize = xFont.attrib["Size"]
                    xfBold = xFont.attrib["Bold"]
                    xfItalic = xFont.attrib["Italic"]
                    if "Color" in list(xFont.attrib.keys()):
                      xfColor = xFont.attrib["Color"]
                    else:
                      xfColor = '#000000'
                
                xSends = button.findall ("ns1:Send", ns)
                slist = []
                if len(xSends):
                    slist = []
                    for xSend in xSends:
                        smap = {}
                        xsDelay = xSend.attrib["Delay"]
                        xsRequestName = xSend.attrib["RequestName"]
                        smap['Delay'] = xsDelay
                        smap['RequestName'] = xsRequestName
                        if len (xsRequestName) > 0:
                            slist.append (smap)
                if len (slist):
                    # print str(slist)
                    self.dBtnSend[str (slist)] = slist
                    # self.dBtnSend[xText] = slist
                
                xfSize = str (int (float (xfSize) * self.scf))
                
                if xrLeft < 0: xrLeft = 0
                if xrTop < 0: xrTop = 0
                
                xfBold = 'bold' if xfBold == '1' else 'normal'
                xfItalic = 'italic' if xfItalic == '1' else 'roman'
                
                lFont = tkinter.font.Font (family=xfName, size=xfSize, weight=xfBold)
                
                frame = tk.Frame (self.ddt, width=xrWidth, height=xrHeight)
                frame.place (x=xrLeft, y=xrTop)
                self.dFrames.append (frame)
                
                if '::btn:' not in xText:
                    obj = tk.Button (frame, text=xText, font=lFont, relief=tk.GROOVE,
                                     command=lambda key=str (slist), btn=xText: self.buttonPressed (btn, key))
                else:
                    gifname = 'graphics/' + xText.split ('|')[1] + '.gif'
                    gifname = gifname.replace ('\\', '/')
                    gifname = mod_db_manager.extract_from_ddt_to_cache(gifname)
                    if gifname:
                        self.images.append (tk.PhotoImage (file=gifname))
                        x1 = self.images[-1].width ()
                        y1 = self.images[-1].height ()
                        self.images[-1] = self.images[-1].zoom (3, 3)
                        self.images[-1] = self.images[-1].subsample (x1 * 3 // xrWidth + 1, y1 * 3 // xrHeight + 1)
                        obj = tk.Button (frame, image=self.images[-1], font=lFont, relief=tk.GROOVE,
                                         command=lambda key=str (slist), btn=xText: self.buttonPressed (btn, key))
                
                obj.place (width=xrWidth, height=xrHeight)
                self.dObj.append (obj)

        # clear elm cache
        self.decu.clearELMcache ()

        if restart:
           self.startStop()

        # request to update dInputs
        self.update_dInputs ()

        # load sends
        sends = scr.findall ("ns1:Send", ns)
        if len(sends):
            for send in sends:
                #if send.parentNode.isSameNode (scr):  #minidim check for parent
                sDelay = '0'
                if "Delay" in list(send.attrib.keys()):
                    sDelay = send.attrib["Delay"]
                sRequestName = ''
                if "RequestName" in list(send.attrib.keys ()):
                    sRequestName = send.attrib["RequestName"]
                self.sReq_dl[sRequestName] = sDelay
                self.sReq_lst.append (sRequestName)
        if len (self.sReq_lst):
            self.startScreen ()

    def loadSyntheticScreen(self, rq):

        # stop ratary. Do not read ELM
        restart = False
        if self.start:
           self.startStop()
           restart = True

        read_cmd = self.decu.requests[rq].SentBytes
        if read_cmd[:2]=='21':
            read_cmd = read_cmd[:4]
            write_cmd = '3B'+read_cmd[2:4]
        elif read_cmd[:2]=='22':
            read_cmd = read_cmd[:6]
            write_cmd = '2E'+read_cmd[2:6]

        wc = ''
        set1 = set(self.decu.requests[rq].ReceivedDI.keys())
        set2 = []
        for r in list(self.decu.requests.keys()):
            if self.decu.requests[r].SentBytes.startswith(write_cmd):
                set2 = set(self.decu.requests[r].SentDI.keys())
                if set1 == set2:
                    wc = r
                    break
        del( set1 )
        del( set2 )

        # main frame re-create
        self.ddt.delete('all')
        self.ddt.update_idletasks()

        for o in self.dObj:
            o.destroy() # place_forget()
        for f in self.dFrames:
            f.destroy() # place_forget()

        self.dValue = {}  # value indexed by DataName
        self.iValue = {}  # value indexed by DataName param with choise
        self.iValueNeedUpdate = {}
        self.dReq = {}  # request names
        self.sReq_dl = {}  # delays for requests sent thru starting the screen
        self.sReq_lst = []  # list of requests sent thru starting the screen (order is important)
        self.dDisplay = {}  # displays object for renew
        self.dObj = []  # objects for place_forget
        self.tObj = {}  # objects for text captions
        self.dFrames = []  # container frames
        self.images = []  # images

        max_x = self.ddtcnv.winfo_width() + 1
        max_y = 200 + len(self.decu.requests[rq].ReceivedDI)*40
        bg_color = "16777215"

        # set scroll region
        self.ddtcnv.config(scrollregion=(0, 0, max_x, max_y))
        self.ddt.config(width=max_x, height=max_y, bg=self.ddtColor(bg_color))
        self.ddtcnv.xview_moveto(0)
        self.ddtcnv.yview_moveto(0)

        self.ddt.event_add('<<RightClick>>', '<Button-2>', '<Button-3>')

        xfSize = str(int(float(20) * self.scf))
        lFont = tkinter.font.Font(family="Arial", size=xfSize)

        xText = self.decu.requests[rq].SentBytes + ' - ' + rq

        self.ddt.create_rectangle(max_x * 0.01, 10, max_x * 0.98, 60,
                                  fill='yellow', outline='gold')
        self.ddt.create_text(max_x//2, 50, text=xText, width=max_x, anchor='s', font=lFont)

        xfSize = str(int(float(10) * self.scf))
        lFont = tkinter.font.Font(family="Arial", size=xfSize)
        pn = 0
        for xText,zzz in sorted(list(self.decu.requests[rq].ReceivedDI.items()), key=lambda item: item[1].FirstByte):

            pn = pn + 1

            if self.translated.get():
                tText = self.decu.translate(xText)
            else:
                tText = xText

            yTop = 30 + pn * 40

            self.dDisplay[xText] = 1

            self.ddt.create_rectangle(max_x * 0.01, yTop-1, max_x * 0.98, yTop + 35,
                                      fill='alice blue', outline='cyan')

            id = self.ddt.create_text(max_x * 0.02, yTop+18, text=tText, font=lFont, width=max_x // 2, anchor='w')
            self.tObj[id] = xText

            frame = tk.Frame(self.ddt, width=max_x // 2, height=35, relief=tk.GROOVE, borderwidth=0)

            frame.place(x=max_x // 2 - max_x * 0.02, y=yTop)
            self.dFrames.append(frame)

            if xText not in list(self.dValue.keys()):
                self.dValue[xText] = tk.StringVar()
                self.dValue[xText].set(mod_globals.none_val)
                if xText in list(self.decu.req4data.keys()) and self.decu.req4data[xText] in list(self.decu.requests.keys()):
                    self.dReq[self.decu.req4data[xText]] = self.decu.requests[self.decu.req4data[xText]].ManuelSend

            obj = tk.Label(frame, text=self.dValue[xText], relief=tk.GROOVE, borderwidth=1, font=lFont,
                           textvariable=self.dValue[xText])

            obj.bind('<<RightClick>>', lambda event, tag=xText: self.rightButtonClicked(event, tag))

            if len(wc)==0:
                obj.place(width=max_x // 2, height=35)
                self.dObj.append(obj)
            else:
                obj.place(width=max_x // 4, height=35)
                self.dObj.append(obj)

                if xText not in list(self.iValue.keys()):
                    if xText not in list(self.dValue.keys()):
                        self.dValue[xText] = tk.StringVar()
                    if xText in list(self.decu.req4data.keys()) and self.decu.req4data[xText] in list(self.decu.requests.keys()):
                        self.dReq[self.decu.req4data[xText]] = self.decu.requests[self.decu.req4data[xText]].ManuelSend
                    self.iValue[xText] = tk.StringVar()
                    self.iValueNeedUpdate[xText] = True

                if xText in list(self.decu.datas.keys()) and len(list(self.decu.datas[xText].List.keys())):
                    optionList = []
                    if xText not in list(self.iValue.keys()):
                        self.iValue[xText] = tk.StringVar()
                        self.iValueNeedUpdate[xText] = True
                    for i in list(self.decu.datas[xText].List.keys()):
                        optionList.append(hex(int(i)).replace("0x", "").upper() + ':' + self.decu.datas[xText].List[i])
                    self.iValue[xText].set(optionList[0])
                    obj = tk.OptionMenu(frame, self.iValue[xText], *optionList)
                else:
                    self.iValue[xText].set('Enter here')
                    obj = tk.Entry(frame, relief=tk.GROOVE, borderwidth=1, font=lFont, textvariable=self.iValue[xText])

                obj.place(width=max_x//4, x=max_x//4, height=35)
                self.dObj.append(obj)

        if len(wc) > 0:
            slist = []
            smap = {}
            smap['Delay'] = 1000
            smap['RequestName'] = wc
            slist.append(smap)
            self.dBtnSend[str(slist)] = slist

            pn = pn + 1
            yTop = 30 + pn * 40

            frame = tk.Frame(self.ddt, width=max_x//4, height=35)
            frame.place(x=max_x*0.75 - max_x * 0.02, y=yTop)
            self.dFrames.append(frame)

            bobj = tk.Button(frame, text="Write", font=lFont, relief=tk.GROOVE,
                                command=lambda key=str(slist), btn=xText: self.buttonPressed(btn, key))

            bobj.place(width=max_x/4, height=35)
            self.dObj.append( bobj )

        # clear elm cache
        self.decu.clearELMcache ()

        # restart if need
        if restart:
           self.startStop()

        # request to update dInputs
        self.update_dInputs ()

        self.sReq_lst.append (rq)
        self.startScreen ()


def main():
    print('exit')


if __name__ == '__main__':
    main ()
