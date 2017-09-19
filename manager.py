#!/usr/bin/python

##Copyright (C) 2009 RobotCub Consortium, European Commission FP6 Project IST-004370
##Author Lorenzo Natale
##email:   <lorenzo.natale>@robotcub.org
##website: www.robotcub.org
##Permission is granted to copy, distribute, and/or modify this program
##under the terms of the GNU General Public License, version 2 or any
##later version published by the Free Software Foundation.
##
##A copy of the license can be found at
##http://www.robotcub.org/icub/license/gpl.txt
##
##This program is distributed in the hope that it will be useful, but
##WITHOUT ANY WARRANTY; without even the implied warranty of
##MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
##Public License for more details


## Added timeout for process termination.
## Added log in temp, cleaned up debug messages to terminal.
## 10/06/2010. Added portableKill() function to ensure we have a portable
## way to terminate a process with windows+python < 2.6

## Feb 08 2011 -- Applied scrollbarpatch from Philipp Robbel. 

import sys
import time
import xml.dom.minidom
import subprocess
import os
import signal
import datetime
from Tkinter import *

# see portableKill function
import ctypes

# a couple of constants
PROCESS_TIMEOUT=240           #seconds
PROCESS_POLL_INTERVAL=0.05    #seconds

## ensure portable way to kill a process
## this works on python < 2.6 (which does not implement
## kill() or terminate()).
def portableKill(theprocess):
    if os.name == 'posix':
        os.kill(theprocess.pid, signal.SIGKILL)
    elif os.name == 'nt':                
        PROCESS_TERMINATE = 1
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, theprocess.pid)
        ctypes.windll.kernel32.TerminateProcess(handle, -1)
        ctypes.windll.kernel32.CloseHandle(handle)


class ModuleData:
    def __init__(self, name, arguments, node, tag, workdir, ioNode):
        self.name = name
        self.parameters = arguments
        self.node = node
        self.tag=tag
        self.stdioNode=ioNode
        self.workdir=workdir

class EntryModule:
    def __init__(self, frame, name, arguments, node, tag, workdir, ioNode):
        self.entryName=Entry(frame)
        self.entryName.insert(END, name)

        self.parameters=arguments

        self.entryNode=Entry(frame)
        self.entryNode.insert(END, node)

        self.entryTag=Entry(frame)
        self.entryTag.insert(END, tag)

        self.entryIoNode=Entry(frame)
        self.entryIoNode.insert(END, ioNode)
        
        self.hold = IntVar()
        self.checkHold=Checkbutton(frame, variable=self.hold)
        self.checkHold.var = self.hold


        self.runningFlag=False
        self.update()

        self.workdir=workdir

    def update(self):
        if self.runningFlag:
            self.entryName.config(foreground="#00A000")
        else:
            self.entryName.config(foreground="#A00000")

class Connection:
    def __init__(self, input, output, protocol):
        self.input=input
        self.output=output
        self.protocol=protocol

class EntryDependency:
    def __init__(self, frame, name):
        self.entry=Entry(frame)
        self.entry.insert(END, name)
        self.flag=IntVar()
        self.check=Checkbutton(frame, variable=self.flag)
        self.check.config(state=DISABLED,disabledforeground="#00A000")
        self.check.var=self.flag

class EntryConnection:
    def __init__(self, frame, outputP, inputP, protocol):
        self.inEntry=Entry(frame)
        self.inEntry.insert(END, inputP)
        self.inFlag=IntVar()
        self.inCheck=Checkbutton(frame, variable=self.inFlag)
        self.inCheck.var=self.inFlag

        self.outEntry=Entry(frame)
        self.outEntry.insert(END, outputP)
        self.outFlag=IntVar()
        self.outCheck=Checkbutton(frame, variable=self.outFlag)
        self.outCheck.var=self.outFlag

        self.protEntry=Entry(frame)
        self.protEntry.insert(END, protocol)
        self.connFlag=IntVar()

        self.connCheck=Checkbutton(frame, variable=self.connFlag)
        self.connCheck.config(state=DISABLED,disabledforeground="#00A000")
        self.connCheck.var=self.connFlag

        self.update()

    def update(self):
        if self.inFlag.get():
            self.inEntry.config(foreground="#00A000")
        else:
            self.inEntry.config(foreground="#A00000")

        if self.outFlag.get():
            self.outEntry.config(foreground="#00A000")
        else:
            self.outEntry.config(foreground="#A00000")

class Dependencies:
    ports=[]
    nodes=[]

class AppData:
    dependencies=Dependencies()

    def __init__(self):
        self.modules=[]
        self.connections=[]

    def setName(self, name):
        self.name = name

    def getName(self):
        return self.name

    def setLogFilename(self, filename):
        self.logfilename=filename

    def getLogFilename(self):
        return self.logfilename

    def pushPortDependency(self, portname):
        self.dependencies.ports.append(portname)
        self.dependencies.ports=list(set(self.dependencies.ports))

    def pushNodeDependency(self, node):
        self.dependencies.nodes.append(node)
        self.dependencies.nodes=list(set(self.dependencies.nodes))

    def pushModuleDetached(self, module, arguments, node, tag, workdir):
        nm=ModuleData(module, arguments, node, tag, workdir, "")
        self.modules.append(nm)

    def pushModuleWithConsole(self, module, arguments, node, tag, workdir, stdioNode):
        nm=ModuleData(module, arguments, node, tag, workdir, stdioNode)
        self.modules.append(nm)

    def pushConnection(self, output, input, prot):
        nc=Connection(input, output, prot)
        self.connections.append(nc)

    def display(self, log):
        log.write("------------\n")
        log.write("--- "+self.name+"\n")
        log.write("-- Dependencies:\n")
        log.write("-Ports:\n")
        for p in self.dependencies.ports:
            log.write(p)

        log.write("-Nodes:\n")
        for n in self.dependencies.nodes:
            log.write(n)

        log.write("\n-- Modules:")
        for mod in self.modules:
            log.write(mod.name)
            log.write(mod.parameters)
            log.write("on")
            log.write("mod.node")
            if mod.workdir!="":
                log.write("workdir")
                log.write(mod.workdir)
            else:
                log.write("\n")

        log.write("-- Connections:\n")
        for c in self.connections:
            log.write(c.output)
            log.write(" --> ")
            log.write(c.input)
            log.write("prot")
            log.write(c.protocol)

        log.write("------------\n")

class Window:
    def __init__(self, master, moduleData):
        frame=Toplevel()
        self.master=frame
        self.module=moduleData

        if moduleData.parameters!="":
            top=Frame(frame)
            top.pack()
            Label(top, text='Parameters:').grid(row=0, column=0, sticky=W)

            bottom=Frame(frame)
            bottom.pack()
            self.pList=moduleData.parameters.split('--')

            r=1
            for e in self.pList:
                if (len(e)>0):
                    v=e.split(' ', 1)
                    tmp=Entry(bottom)
                    entries=len(v)
                    tmp.insert(END, '--'+v[0])
                    tmp.grid(row=r,column=0)

                    tmp=Entry(bottom)

                    if (entries>1):
                        tmp.insert(END, v[1])

                    tmp.grid(row=r,column=1)
                    r=r+1


        if (moduleData.workdir!=""):
            tmp=Frame(frame)
            tmp.pack()
            Label(tmp, text='Working directory:').grid(row=0, column=0)
            tmpE=Entry(tmp)
            tmpE.insert(END, moduleData.workdir)
            tmpE.grid(row=1, column=0, sticky=W)
            
 
        #finally place window close to top left corner
        frame.update_idletasks() #update current geometry
        width=frame.winfo_width()
        height=frame.winfo_height()
        rootx=master.winfo_rootx()
        rooty=master.winfo_rooty()
        frame.geometry('%dx%d+%d+%d' %(width, height, rootx, rooty))
        frame.title(moduleData.entryName.get())

class App:
    application=AppData()
    dependenciesFlag=False

    def __init__(self, master, app):
        self.master=frame
        self.titleFrame=Frame(frame)
        self.titleFrame.pack()
        self.depFrame=Frame(frame)
        self.depFrame.pack()
        self.modFrame=Frame(frame)
        self.modFrame.pack()
        self.connFrame=Frame(frame)
        self.connFrame.pack()
        self.actionsFrame=Frame(frame)
        self.actionsFrame.pack()

        self.application=app

        self.connections=[]
        self.portDep=[]
        self.nodeDep=[]
        self.modules=[]

        Label(self.titleFrame, text="Application Name: "+self.application.name).grid(row=0, column=0, sticky=N+W+E+S)
        tmpFrame=self.depFrame

        r=1
        if (len(self.application.dependencies.ports)>0):
            Label(tmpFrame, text="Dependencies, ports:").grid(row=r,column=0, sticky=W)
            r=r+1

        for port in self.application.dependencies.ports:
            tmp=EntryDependency(tmpFrame, port)
            tmp.check.grid(row=r, column=1, sticky=W)
            tmp.entry.grid(row=r, column=0, sticky=W)
            self.portDep.append(tmp)
            r=r+1

        Label(tmpFrame, text="Dependencies, nodes:").grid(row=r,column=0, sticky=W)

        r=r+1
        for node in self.application.dependencies.nodes:
            tmp=EntryDependency(tmpFrame, node)
            tmp.check.grid(row=r, column=1, sticky=W)
            tmp.entry.grid(row=r, column=0, sticky=W)
            self.nodeDep.append(tmp)
            r=r+1

        tmp=Button(tmpFrame, text="Checkdep", command=self.checkDeps);
        tmp.grid(row=(r)/2, column=2, rowspan=r-1, sticky=S+N+E+W)
        r=r+1

        tmpFrame=self.modFrame
        Label(tmpFrame, text="Module:").grid(row=r, column=0, sticky=W)
        Label(tmpFrame, text="On node:").grid(row=r, column=1, sticky=W)
        Label(tmpFrame, text="Stdio:").grid(row=r, column=2, sticky=W)
        Label(tmpFrame, text="Tag:").grid(row=r, column=3, sticky=W)
        Label(tmpFrame, text="Hold:").grid(row=r, column=4, sticky=W)
        
        r=r+1

        for mod in self.application.modules:
            if (mod.stdioNode!=""):
                tmpModule=EntryModule(tmpFrame, mod.name, mod.parameters, mod.node, mod.tag, mod.workdir, mod.stdioNode)
            else:
                tmpModule=EntryModule(tmpFrame, mod.name, mod.parameters, mod.node, mod.tag, mod.workdir, "none")

            self.modules.append(tmpModule)

            tmpModule.entryName.grid(row=r, column=0, sticky=W)
            tmpModule.entryName.config(width=12)

            tmpModule.entryNode.grid(row=r, column=1, sticky=W)
            tmpModule.entryNode.config(width=12)

            tmpModule.entryIoNode.grid(row=r, column=2, sticky=W)
            tmpModule.entryIoNode.config(width=12)

            tmpModule.entryTag.grid(row=r, column=3, sticky=W)
            tmpModule.entryTag.config(width=12)
            
            tmpModule.checkHold.grid(row=r, column=4, sticky=W)

            tmp=Button(tmpFrame, text="Run", command=lambda i=tmpModule:self.runModule(i));
            tmp.grid(row=r, column=5, sticky=W)
            tmp=Button(tmpFrame, text="Ctrl-c", command=lambda i=tmpModule:self.quitModule(i));
            tmp.grid(row=r, column=6, sticky=W)
            tmp=Button(tmpFrame, text="Kill", command=lambda i=tmpModule:self.killModule(i));
            tmp.grid(row=r, column=7, sticky=W)
            tmp=Button(tmpFrame, text="Check", command=lambda i=tmpModule:self.checkModule(i));
            tmp.grid(row=r, column=8, sticky=W)
            tmp=Button(tmpFrame, text="Params", command=lambda i=tmpModule:self.dispParameters(i));
            tmp.grid(row=r, column=9, sticky=W)
            
            r=r+1

        tmpFrame=self.connFrame
        Label(tmpFrame, text="Connections:").grid(row=r, column=0, sticky=W)
        r=r+1

        for conn in self.application.connections:
            tmp=EntryConnection(tmpFrame, conn.output, conn.input, conn.protocol)
            tmp.outEntry.grid(row=r, column=0, sticky=W)
            Label(tmpFrame, text="to:").grid(row=r, column=1)
#           tmp.outCheck.grid(row=r, column=1, sticky=W)
            tmp.inEntry.grid(row=r, column=2, sticky=W)
#           tmp.inCheck.grid(row=r, column=3, sticky=W)
            Label(tmpFrame, text="prot:").grid(row=r, column=3)
            tmp.protEntry.grid(row=r, column=4, sticky=W)
            tmp.connCheck.grid(row=r, column=5, sticky=W)
            self.connections.append(tmp)
            r=r+1

        tmpFrame=self.actionsFrame
        tmp=Button(tmpFrame, text="Run Modules", command=self.runModules)
        tmp.grid(row=r, column=0)
        tmp=Button(tmpFrame, text="Stop Modules", command=self.quitModules)
        tmp.grid(row=r, column=1)
        tmp=Button(tmpFrame, text="Kill Modules", command=self.killModules)
        tmp.grid(row=r, column=3)
        tmp=Button(tmpFrame, text="Update", command=self.update)
        tmp.grid(row=r, column=4)
        tmp=Button(tmpFrame, text="Connect", command=self.connectPorts)
        tmp.grid(row=r, column=5)
        tmp=Button(tmpFrame, text="Disconnect", command=self.disconnectPorts)
        tmp.grid(row=r, column=6)
        r=r+1

        # open log file
        log=self.application.getLogFilename()
        self.logfile=open(log,"w")
        print "Logging to: "+log
        self.logfile.writelines("== "+self.application.getName()+" ==\n")
        self.logfile.writelines("Log started on ")
        self.logfile.writelines(datetime.datetime.now().strftime("%A (%a) %d/%m/%Y\n"))

        self.application.display(self.logfile)

        #finally check dependencies and ports
        self.checkDeps()
        self.checkPorts()

    def spawnProcess(self, cmd):
        print "Running: ", str(cmd)
        self.logfile.writelines("Running"+str(cmd)+"\n")
        fin_time = time.time() + PROCESS_TIMEOUT
        p=subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	#, stdout=self.logfile, stderr=self.logfile)
        while (p.poll()==None and  fin_time > time.time()):
            #self.logfile.writelines(p.communicate())
	    #self.logfile.writelines(p.stdout.read())
            time.sleep(PROCESS_POLL_INTERVAL)
               
        if (fin_time < time.time()):
            self.logfile.writelines("Process timed out killing "+str(cmd)+"\n")
            print "--> Error process timed out",
            print "you can try increasing the timeout time",
            print "however this is probably due to a problem to your",
            print "yarp network (address conflict?)"
            print "See log file /tmp/"+self.application.getName()+".log"
            print "I'll now kill ", str(cmd), ""
            #os.kill(p.pid, signal.SIGKILL)
            portableKill(p)
            
            ret = 1
        else:
            ret = p.returncode
            
        return ret

    def checkModules(self):
        for mod in self.modules:
            self.checkModule(mod)

    def checkPorts(self):
        for port in self.connections:
            cmd=['yarp', 'exists', port.outEntry.get()]
#            ret=subprocess.Popen(cmd).wait()
            ret=self.spawnProcess(cmd)
            connectionFlag=True
            if ret!=0:
                port.outFlag.set(0)
            else:
                port.outFlag.set(1)

            cmd=['yarp', 'exists', port.inEntry.get()]
            ret=self.spawnProcess(cmd)

            if ret!=0:
                port.inFlag.set(0)
            else:
                port.inFlag.set(1)

            ret=1
            if port.inFlag.get() and port.outFlag.get():
                cmd=['yarp', 'exists', port.outEntry.get(), port.inEntry.get()]
                print cmd
                ret=self.spawnProcess(cmd)
    
            if ret!=0:
                port.connFlag.set(0)
            else:
                port.connFlag.set(1)

            port.update()

    def update(self):
        self.checkModules()
        self.checkPorts()
        
    def connectPorts(self):
        self.checkPorts()

        for port in self.connections:
            if port.inFlag.get() and port.outFlag.get():
                cmd=['yarp', 'connect', port.outEntry.get(), port.inEntry.get(), port.protEntry.get()]
                self.spawnProcess(cmd)

                port.update()

        self.checkPorts()

    def disconnectPorts(self):
        self.checkPorts()

        for port in self.connections:
            if port.inFlag.get() and port.outFlag.get():
                cmd=['yarp', 'disconnect', port.outEntry.get(), port.inEntry.get()]
                self.spawnProcess(cmd)

                port.update()

        self.checkPorts()

    def quitModule(self, mod):
        node=mod.entryNode.get()
        tag=mod.entryTag.get()

        cmd=['yarprun', '--on', '/'+node, '--sigterm', tag]
        ret=self.spawnProcess(cmd)

    def killModule(self, mod):
        node=mod.entryNode.get()
        tag=mod.entryTag.get()

        cmd=['yarprun', '--on', '/'+node, '--kill', tag, '9']
        ret=self.spawnProcess(cmd)

    def runModule(self, mod):
        #ret=self.checkDeps()

        #if not ret:
            #print "Sorry some dependencies were not met, cannot run the application"
            #return

        self.checkModule(mod)

        if mod.runningFlag:
            print "Module already running, skipping"
            return

        node=mod.entryNode.get()
        tag=mod.entryTag.get()
        stdioNode=mod.entryIoNode.get()
        node=mod.entryNode.get()
        parameters=mod.parameters
        name=mod.entryName.get()
        hold = ""
        if (mod.hold.get()):
            hold = "--hold"
        workdir=mod.workdir
        
        if (stdioNode == "none"):
            if(workdir == ""):
                cmd=['yarprun', '--cmd', '\"'+name+' '+parameters+'\"', '--on', '/'+node, '--as', tag]
            else:
                cmd=['yarprun', '--cmd', '\"'+name+' '+parameters+'\"', '--on', '/'+node, '--as', tag, '--workdir',workdir]
        else:
            if(workdir == ""):
                cmd=['yarprun', '--cmd', '\"'+name+' '+parameters+'\"', '--on', '/'+node, '--as', tag, '--stdio', '/'+stdioNode, hold]
            else:
                cmd=['yarprun', '--cmd', '\"'+name+' '+parameters+'\"', '--on', '/'+node, '--as', tag, '--stdio', '/'+stdioNode, hold, '--workdir',workdir]

        ret=self.spawnProcess(cmd)

        self.checkModule(mod)
            
    def checkModule(self, mod):
        node=mod.entryNode.get()
        tag=mod.entryTag.get()
        
        cmd=['yarprun', '--on','/'+node,'--isrunning', tag]
        ret=self.spawnProcess(cmd)

        if ret==0:
            mod.runningFlag=True
            mod.update()
        else:
            mod.runningFlag=False
            mod.update()
        
    def runModules(self):
        print "-- Running modules"

        #ret=self.checkDeps()
        #if not ret:
            #print "Sorry some dependencies were not met, cannot run the application"
            #return

        self.checkModules()

        for mod in self.modules:
            self.runModule(mod)
            
    def quitModules(self):
        print "-- Quitting modules"

        #ret=self.checkDeps()

        #if not ret:
            #print "Sorry some dependencies were not met, cannot stop the application"
            #return

        for mod in self.modules:
            self.quitModule(mod)

    def killModules(self):
        print "-- Stopping modules"

        #ret=self.checkDeps()

        #if not ret:
            #print "Sorry some dependencies were not met, cannot stop the application"
            #return

        for mod in self.modules:
            self.killModule(mod)

    def checkDeps(self):
        print "-- Checking port dependencies:"

        dependenciesFlag=True

        for dep in self.portDep:
            cmd=['yarp', 'exists', dep.entry.get()]
            ret=self.spawnProcess(cmd)
            if ret==0:
                dep.flag.set(1)
            else:
                dep.flag.set(0)
                dependenciesFlag=False

        #print "-- Checking node dependencies:"
        for dep in  self.nodeDep:
            cmd=['yarp', 'exists', '/'+dep.entry.get()]
            ret=self.spawnProcess(cmd)
            if ret==0:
                dep.flag.set(1)
            else:
                dep.flag.set(0)
                dependenciesFlag=False

        return dependenciesFlag

    def dispParameters(self, moduleData):
        w=Window(self.master, moduleData)

# From http://effbot.org/zone/tkinter-autoscrollbar.htm
class AutoScrollbar(Scrollbar):
    # a scrollbar that hides itself if it's not needed.  only
    # works if you use the grid geometry manager.
    def set(self, lo, hi):
        if float(lo) <= 0.0 and float(hi) >= 1.0:
            # grid_remove is currently missing from Tkinter!
            self.tk.call("grid", "remove", self)
        else:
            self.grid()
        Scrollbar.set(self, lo, hi)
    def pack(self, **kw):
        raise TclError, "cannot use pack with this widget"
    def place(self, **kw):
        raise TclError, "cannot use place with this widget"

def printUsage(scriptName):
    print scriptName, ": python gui for parsing applications xml files"
    print "Usage:"
    print scriptName, 
    print "app.xml"
    print "app.xml: application descriptor file"

def fileExists(f):

    try:
        file=open(f)
    except IOError:
        return 0
    else:
        return 1

if __name__ == '__main__':
  
    #first check arguments
    argc = len(sys.argv)

    if (argc!=2):
        printUsage("manager.py")
        sys.exit(1)

    appFile = sys.argv[1]
    found=fileExists(appFile)
    
    if found:
        fullPathApp=appFile
    else:
        print appFile,
        print " not in local directory"
        robotName = os.environ.get("ICUB_ROBOTNAME")
        appDir='../../'+robotName+'/scripts/'
        print "Trying in",
        print appDir
        found=fileExists(appDir+appFile)
        if (not found):
            print "Sorry, I give up"
            sys.exit(1)
        fullPathApp=appDir+appFile

    appDescription = xml.dom.minidom.parse(fullPathApp)

    applicationList = []

    applications = appDescription.getElementsByTagName("application")
    for app in applications:
        napp=AppData();

        name = app.getElementsByTagName("name")[0].firstChild.data
        print "Application ", name

        napp.setName(name)

        deps=app.getElementsByTagName("dependencies").item(0)
        if (deps!=None):
          for p in deps.getElementsByTagName("port"):
                napp.pushPortDependency(p.firstChild.data)

        for mod in app.getElementsByTagName("module"):
            name = mod.getElementsByTagName("name")[0].firstChild.data
            node = mod.getElementsByTagName("node")[0].firstChild.data

            #protect against nodes whose names start with /
            if (node[0]=='/'):
                print "WARNING: <node> entry should NOT contain trailing '/'"
                node=node[1:]

            tag = mod.getElementsByTagName("tag")[0].firstChild.data

            if (mod.getElementsByTagName("parameters").item(0)==None):
                parameters=""
            else:
                parametersNode = mod.getElementsByTagName("parameters")[0]
                #allow empty sections
                if (parametersNode.firstChild != None):
                    parameters = parametersNode.firstChild.data

                    # wanr about wrapping parameters with ""
                    if (parameters[0]=="\""):
                        print "WARNING: detected parameter list starting with \" (are you wrapping parameters with \"\"?)"
                        parameters=parameters[1:]
                    if (parameters[len(parameters)-1]=="\""):
                        print "WARNING: detected parameter list ending with \" (are you wrapping parameters with \"\"?)"
                        parameters=parameters[:len(parameters)-2]
                                          
                    # warn about use of ""
                    if (parameters=="\"\""):
                       print "WARNING: do not use empty parameter list \"\""
                       parameters=""
                else:
                    parameters=""

            if (mod.getElementsByTagName("workdir").item(0)==None):
                workdir=""
            else:
                workdirNode= mod.getElementsByTagName("workdir")[0]
                if (workdirNode.firstChild!=None):
                    workdir=workdirNode.firstChild.data
                else:
                     workdir=""
                     
            napp.pushNodeDependency(node)

            stdioNode=mod.getElementsByTagName("stdio").item(0)
            if (stdioNode != None):
                stdNode=stdioNode.firstChild.data
                napp.pushModuleWithConsole(name, parameters, node, tag, workdir, stdNode)
                napp.pushNodeDependency(stdNode)
            else:
                napp.pushModuleDetached(name, parameters, node, tag, workdir)

        for c in app.getElementsByTagName("connection"):
            input=c.getElementsByTagName("input").item(0)
            if (input != None):
                print "WARNING: found obsolete tag <input>, please use <to> instead"
                input=input.firstChild.data
            else:
                input=(c.getElementsByTagName("to")[0].firstChild.data)

            output=c.getElementsByTagName("output").item(0)
            if (output != None):
                print "WARNING: found obsolete tag <output>, please use <from> instead"
                output=output.firstChild.data
            else:
                output=(c.getElementsByTagName("from")[0].firstChild.data)

            protocol=c.getElementsByTagName("protocol").item(0)
            if (protocol != None):
                napp.pushConnection(output, input, protocol.firstChild.data)
            else:
                napp.pushConnection(output, input, "tcp")

        # getting temp directory
        tmpPath  = os.getenv("TMP");
	if (tmpPath==None):
		tmpPath="/tmp"
        
        logfilename=tmpPath+"/"+napp.getName()+".log"
        napp.setLogFilename(logfilename)
        applicationList.append(napp)



#    for app in applicationList:
#        app.display()

    root = Tk()

    # create scrolled canvas
    vscrollbar = AutoScrollbar(root)
    vscrollbar.grid(row=0, column=1, sticky=N+S)
    hscrollbar = AutoScrollbar(root, orient=HORIZONTAL)
    hscrollbar.grid(row=1, column=0, sticky=E+W)
    
    canvas = Canvas(root,
                    yscrollcommand=vscrollbar.set,
                    xscrollcommand=hscrollbar.set)
    canvas.grid(row=0, column=0, sticky=N+S+E+W)
    
    vscrollbar.config(command=canvas.yview)
    hscrollbar.config(command=canvas.xview)
    
    # make the canvas expandable
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)
    
    # create canvas contents
    frame = Frame(canvas)
    frame.rowconfigure(1, weight=1)
    frame.columnconfigure(1, weight=1)
    
    # The application
    app = App(frame, applicationList[0])
    
    canvas.create_window(0, 0, anchor=NW, window=frame)
    frame.update_idletasks()
    canvas.config(scrollregion=canvas.bbox("all"))
    # resize canvas
    frame.update()
    canvas['width'] = frame.winfo_width() + 10
    height = frame.winfo_height()
    if height > 700:
        height = 700
    canvas['height'] = height

    root.title("Application Manager")
    root.mainloop()
    
