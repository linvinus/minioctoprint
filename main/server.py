#
#  mini server for file upload to marlin with USB flash drive device
#  implemented basic octoprint protocol for file uploading and start printing, if requested
#
#  pmount is used to mount/unmount disk without root priveleges
#  
#  please set
#       printer_mountpoint -  mountpoint where to mount your marlin disk device
#
#

from http.server import BaseHTTPRequestHandler, HTTPServer
#from socketserver import ThreadingMixIn


from urllib.parse import urlparse, parse_qs
from cgi import  FieldStorage

import time
import os
import sys

#for vfat name 8.3
import fcntl
import struct
import serial
import json

VFAT_IOCTL_READDIR_BOTH = -2112327167                                                                                                 
VFAT_IOCTL_READDIR_SHORT = -2112327166                                                                                                
BUFFER_SIZE = 536                                                                                                                     
BUFFER_FORMAT = '=8xH256s2x8xH256s2x'

'''
Prints the directory tree below the given FAT partition path.
Outputs both the long and short (8.3 format) file and directory names.
'''

class FATParser(object):
    def __init__(self, topdir):
        # Store the top directory
        self.topdir = topdir

        # Create an empty dictionary to store the paths
        self.paths = {}

        # A buffer to hold the IOCTL data
        self.buffer = bytearray(BUFFER_SIZE)

        # Walk the directory tree
        for root, dirs, files, rootfd in os.fwalk(topdir):
            self.get_directory_entries(root, rootfd)

    def get_directory_entries(self, directory_name, directory_fd):

        # Get the path relative to the top level directory
        relative_path = os.path.relpath(directory_name, self.topdir)

        # If we don't have it, it's the top level directory so we
        # seed the paths dictionary. If we have it, get the shortname
        # for the directory (collected one level up).
        if relative_path not in self.paths:
            self.paths[relative_path] = {
                'shortname': relative_path,
                'files': []}
            current_path_shortname = relative_path
        else:
            current_path_shortname = self.paths[relative_path]['shortname']

        while True:

            # Get both names for the next directory entry using a ioctl call.
            result = fcntl.ioctl(
                directory_fd,
                VFAT_IOCTL_READDIR_BOTH,
                self.buffer)

            # Have we finished?
            if result < 1:
                break

            # Interpret the resultant bytearray
            # sl = length of shortname
            # sn = shortname
            # ll = length of longname
            # ln = longname
            sl, sn, ll, ln = struct.unpack(
                BUFFER_FORMAT,
                self.buffer)

            # Decode the bytearrays into strings
            # If longname has zero length, use shortname
            shortname = sn[:sl].decode()
            if ll > 0:
                filename = ln[:ll].decode()
            else:
                filename = shortname

            # Don't process . or ..
            if (filename != '.') and (filename != '..'):
                # Check whether it's a directory
                fullname = os.path.join(directory_name, filename)
                if os.path.isdir(fullname):
                    # Create the paths entry
                    self.paths[os.path.relpath(fullname, self.topdir)] = {
                        'shortname': os.path.join(
                            current_path_shortname, shortname),
                        'files': []}
                else:
                    self.paths[relative_path]['files'].append({
                        'shortname': shortname,
                        'fullname': fullname,
                        'filename': filename})

    def get83(self,fname):
        for f in self.paths['.']['files']:
            print('\t {} --> {}'.format(f['filename'], f['shortname']))
            if f['filename'] == fname:
              return f['shortname']
        return None


      
    def display(self):
        for path in self.paths:
            print('{} --> {}'.format(path, self.paths[path]['shortname']))
            for f in self.paths[path]['files']:
                print('\t {} --> {}'.format(f['filename'], f['shortname']))

class PrintSerial(serial.Serial):
  
    def ser_write(self,S):
      print("send:'%s'" %  S)
      # ~ ser = Octohandler.serial_connection
      self.write(bytes("%s\r\n" % S, 'utf8')) #listfiles

    def wait_ok(self,error = '', ok = 'ok',count=5):
      ok = ok.strip()
      error = error.strip()
      print("waiting... err=%s ok=%s" %( error, ok) )
      while(count > 0):
        L = self.readline()
        if not L:
          #time.sleep(1)
          #timeout is set in serial open, 1s
          count-=1
          continue
        L = L.decode('utf-8')
        print(L)
        if  error == True and L.find(error) != -1:
          print("found error = '%s'" % error)
          return False
        if L.find(ok) != -1:
          return True
      print("not found ok")
      return False
  

class Octohandler(BaseHTTPRequestHandler):
    prev_blockId=""
    printer_mountpoint = '/media/octoprint/7794-45CF'

    def _set_headers(self):
        self.send_response(200, 'Hello')
        self.send_header('accept-ranges', 'bytes')
        self.send_header('Content-type', 'text/plain')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

    def do_GET(self):
        print(self.headers,self.path)
        error_answer = '''
          {
          "success": "FALSE",
          "fieldErrors": [{"fieldError":"string","fieldName":"string"}],
          "globalErrors": ["%s"]
          }
        '''
        printer_answer = '''
{
  "temperature": {
    "tool0": {
      "actual": 0,
      "target": 0.0,
      "offset": 0
    },
    "tool1": {
      "actual": 25.3,
      "target": null,
      "offset": 0
    },
    "bed": {
      "actual": 0,
      "target": 0.0,
      "offset": 5
    }
  },
  "sd": {
    "ready": "true"
  },
  "state": {
    "text": "Operational",
    "flags": {
      "operational": "true",
      "paused": "false",
      "printing": "false",
      "cancelling": "false",
      "pausing": "false",
      "sdReady": "true",
      "error": "false",
      "ready": "true",
      "closedOrError": "false"
    }
  }
}
        '''
        job_answer = '''
{
  "job": {
    "file": {
      "name": "whistle_v2.gcode",
      "origin": "local",
      "size": 1468987,
      "date": 1378847754
    },
    "estimatedPrintTime": 8811,
    "filament": {
      "length": 810,
      "volume": 5.36
    }
  },
  "progress": {
    "completion": 0.2298468264184775,
    "filepos": 337942,
    "printTime": 276,
    "printTimeLeft": 912
  },
  "state": "Operational"
}
        '''
        query_components = parse_qs(urlparse(self.path).query)
        if "/api/version" in self.path:
            print("GET /api/version",query_components)
            self.send_response(200)
            self.send_header('Content-type','application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(bytes('{"api":"0.1","server":"1.1.0","text":"OctoPrint 1.3.10"}', 'utf8'))
            return

        if "/api/settings" in self.path:
            print("GET /api/settings",query_components)
            self.send_response(200)
            self.send_header('Content-type','application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(bytes('{"api":"0.1","server":"1.1.0","text":"OctoPrint 1.3.10"}', 'utf8'))
            return

        if "/api/printer" in self.path:
            print("GET /api/printer",query_components)
            self.send_response(200)
            self.send_header('Content-type','application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(bytes( json.dumps(json.loads(printer_answer)), 'utf8'))
            return

        if "/api/job" in self.path:
            print("GET /api/job",query_components)
            self.send_response(200)
            self.send_header('Content-type','application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(bytes(json.dumps(json.loads(job_answer)), 'utf8'))
            return

        self.send_response(404)
        self.send_header('Content-type','application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(bytes(error_answer % ("path not found!!! "+self.path), 'utf8'))
        return

      

    def get_mounts(self):
        with open('/proc/mounts','r') as f:
            mounts = [line.split()[1] for line in f.readlines()]
            return mounts 
        return None


    def do_POST_api_files(self, ser):
        error_answer="%s"

        if "/api/login" in self.path:
              self.send_response(200)
              self.send_header('Content-type','application/json; charset=utf-8')
              self.end_headers()
              self.wfile.write(bytes('{"name":"denis"}', 'utf8'))
              return


        if ser.isOpen():
          ser.flushInput() #flush input buffer, discarding all its contents
          ser.flushOutput()#flush output buffer, aborting current output 
                           #and discard all that is in buffer

        
        ser.ser_write('M27 C') #Get SD print status
        
        if ser.wait_ok(error='SD printing'):
          if not Octohandler.printer_mountpoint in self.get_mounts():
            ser.ser_write('M22') #umount sd card on printer
            if ser.wait_ok():
              print("M22 ok")
            
            print("waiting for printer flash drive, up to 60 seconds")

            for i in range(0,60):  #wait up to 60 seconds
              if Octohandler.printer_mountpoint in self.get_mounts():
               break
              print(i)
              time.sleep(1) #wait for mount

            if not Octohandler.printer_mountpoint in self.get_mounts():              
              self.send_response(404)
              self.send_header('Content-type','application/json; charset=utf-8')
              self.end_headers()
              self.wfile.write(bytes(error_answer % ("printer is not mounted"), 'utf8'))
              return
        else:
          self.send_response(404)
          self.send_header('Content-type','application/json; charset=utf-8')
          self.end_headers()
          self.wfile.write(bytes(error_answer % ("unable to upload while printer is printing"), 'utf8'))
          return


        if "/api/files/local" in self.path or "/api/files/sdcard" in self.path:

          form = FieldStorage(fp=self.rfile,headers=self.headers,environ={'REQUEST_METHOD':'POST','CONTENT_TYPE':self.headers['content-type']})

          filecontent = form['file'].value
          filename    = form['file'].filename
          
          start_printing = False
          
          print("receive %s" % filename)
          #print(form.keys())

          if 'print' in form.keys():
            start_printing = (form['print'].value.lower() == "true")
          
          print("Start to print? ",start_printing) 

          if filecontent:
            #tm = datetime.now().strftime("%Y%m%d%H%M%S.%f")
            file_save="%s/%s" % (Octohandler.printer_mountpoint, os.path.basename(filename))
            binary_file = open(file_save, "w+b")
            binary_file.write(filecontent)
            binary_file.close()

            print("File %s was successfully received" % file_save)

            
            if start_printing:

                fat_parser = FATParser(Octohandler.printer_mountpoint)
                f83 = fat_parser.get83(filename)
                print("name83=%s" % f83)
                if f83:
                    if ser.isOpen():
                      ser.flushInput() #flush input buffer, discarding all its contents
                      ser.flushOutput()#flush output buffer, aborting current output 
                    os.popen('/bin/umount %s' % Octohandler.printer_mountpoint)
                    time.sleep(5)
                    if Octohandler.printer_mountpoint in self.get_mounts():              
                      self.send_response(404)
                      self.send_header('Content-type','application/json; charset=utf-8')
                      self.end_headers()
                      self.wfile.write(bytes(error_answer % ("unable to umount"), 'utf8'))
                      return

                    ser.ser_write('M21') #mount sd card on printer
                    if ser.wait_ok( ok = "SD card ok") == True and ser.wait_ok():
                      print("M21 ok")

                      ser.ser_write('M20') #listfiles
                      ser.wait_ok(ok="End file list")
                      ser.wait_ok() #skip ok

                      ser.ser_write('M23 /%s' % f83) #select
                      if ser.wait_ok(ok="File selected",error="open failed") == True and ser.wait_ok():
                        print("M23 ok")
                        ser.ser_write('M24')        #start
                        if ser.wait_ok():
                          print("M24 ok")
                          print("print was started!!!")
                      else:
                        print("M23 open filed")
                        self.send_response(404)
                        self.send_header('Content-type','application/json; charset=utf-8')
                        self.end_headers()
                        self.wfile.write(bytes(error_answer % ("unable start printing"), 'utf8'))
                        return

            self.send_response(200)
            self.send_header('Content-type','text/html; charset=UTF-8')
            self.end_headers()
            self.wfile.write(bytes("OK", 'utf8'))
            return


        self.send_response(404)
        self.send_header('Content-type','application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(bytes(error_answer % ("path not found!!! " + self.path), 'utf8'))
        return

    def do_POST(self):
        # print(self.headers)
        print(self.headers,self.path)
        # ~ query_components = parse_qs(urlparse(self.path).query)
        # ~ try:
            # ~ content_length = int(self.headers['Content-Length'])
        # ~ except Exception:
            # ~ content_length = 0

        # ~ print(mounts)
        print(sys.argv[1])

        ser = PrintSerial(
            port="/dev/%s" % sys.argv[1],
            baudrate=115200,
            parity=serial.PARITY_ODD,
            stopbits=serial.STOPBITS_TWO,
            bytesize=serial.SEVENBITS,
            timeout=1
        )

        # ~ ser = Octohandler.serial_connection
        ret = self.do_POST_api_files(ser)
        ser.close()
        
        return ret



# ~ class ThreadedHttpServer(ThreadingMixIn, HTTPServer):
    # ~ pass


def run():
    server_address = ('0.0.0.0', 8205)
    print('starting server...%s:%s' % server_address)
    # ~ httpd = ThreadedHttpServer(server_address, Octohandler)
    httpd = HTTPServer(server_address, Octohandler) #single thread 
    print('running server...')
    httpd.serve_forever()
