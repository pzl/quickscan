#!/usr/bin/env python3

import sane
from PIL import TiffImagePlugin
import logging
import socket
import json
from signal import signal, SIGTERM, SIGINT
import atexit
import sys, os
import time
import datetime
import random

"""
Interesting options:

    source: ['ADF Front', 'ADF Back', 'ADF Duplex']
    mode: ['Lineart','Halftone','Gray','Color']
    resolution: 50-600
    ald: 0/1 (auto length detection)
    df_action: ['Default','Continue','Stop']
    buffermode: ['Default','On','Off']
    side: 1/0 (0=front,1=back)
    swdeskew: 0/1
    swdespeck: 0-9
    swcrop: 0/1
    swskip: 0.0-100.0

    top_edge: 0/1
    a3_paper: 0/1
    a4_paper: 0/1
    page_loaded: 0/1
    cover_open: 0/1
"""

logging.basicConfig(level=logging.DEBUG,format="%(asctime)s %(levelname)7s : %(message)s")

NOOP = lambda *x, **y: None

class Client(object):
    """Communication with sccontrol client"""
    def __init__(self, sock, addr):
        super(Client, self).__init__()
        self.sock = sock
        self.addr = addr
        atexit.register(self.cleanup)
        logging.info("got connection from {}".format(addr))

    def cleanup(self):
        logging.debug("cleaning up client socket")
        self.sock.close()


    def _sendb(self, data):
        msglen = len(data).to_bytes(4, byteorder='big')
        self.sock.send(msglen+data)
    def _send(self, string):
        self._sendb(string.encode('utf8'))
    def _sendjson(self, thing):
        return self._send(json.dumps(thing))
    def _getmsg(self):
        pkt_len = self.sock.recv(4)
        if pkt_len == b'':
            return None
        pkt_len = int.from_bytes(pkt_len, byteorder='big')
        nbytes=0
        chunks=[]
        while nbytes < pkt_len:
            chunk = self.sock.recv(min(pkt_len - nbytes, 2048))
            if chunk == b'':
                return None
            chunks.append(chunk)
            nbytes += len(chunk)
        return b''.join(chunks)


    def _get_command(self):
        msg = self._getmsg()
        if msg is None:
            return None,None
        msg = json.loads(msg.decode('utf8'))
        if type(msg) is not dict or 'scan' not in msg:
            return None,None
        scan = bool(msg['scan'])
        opts = msg['options'] if 'options' in msg else {}
        return scan,opts

    def _get_data_req(self):
        msg = self._getmsg()
        if msg is None:
            return None
        page = int(msg.decode('utf8'))
        return page


    def _send_page_data(self, data):
        scaled_data = data.resize((240,320)).tobytes()
        self._sendb(scaled_data)

    def _send_crop_data(self, data):
        w,h = data.size
        x,y = random.randrange(w-240),random.randrange(h-320)
        cropped_data = data.crop((x,y,x+240,y+320)).tobytes()
        self._sendb(cropped_data)

    def send_progress(self, action, *args):
        logging.debug("** sending to client: {} : {}".format(action,args))
        try:
            self._send(":".join([action,*args]))
        except BrokenPipeError:
            logging.debug("client socket closed")
            pass

    def process(self, cb):
        # client should contact us first with options
        cmd,opts = self._get_command()
        if not cmd:
            return

        success,data = cb(opts, self.send_progress)
        if not success:
            logging.debug('scan did not produce images, skipping page-request')
            return
        logging.debug('scan produced images, listening for page requests')
        last_page = None
        page = self._get_data_req()
        while page != None:
            logging.debug('got page request')
            if page < 0 or page >= len(data):
                logging.debug('page request out of range')
                continue
            if last_page != page:
                logging.debug('sending page {}'.format(page))
                self._send_page_data(data[page])
            else:
                logging.debug('already sent page {}, sending crop sample'.format(page))
                self._send_crop_data(data[page])
            last_page = page
            logging.debug('listening for next page request')
            page = self._get_data_req()
        logging.debug('Client process complete')




class PageFeed(object):
    """Page iterator for ADF feed since python-sane doesn't do it right for python3"""
    def __init__(self, dev, cb):
        super(PageFeed, self).__init__()
        self.dev = dev
        self.client_notify = cb
    def __iter__(self):
        return self
    def __del__(self):
        try:
            self.dev.cancel()
        except:# device may have already closed
            pass
    def __next__(self):
        start = time.time()
        try:
            self.client_notify("feed start")
            logging.debug("Feeding a page")
            self.dev.start()
        except sane._sane.error as e:
            if str(e) == 'Document feeder out of documents':
                logging.debug("no page to feed, finished")
                self.client_notify("pages end")
                raise StopIteration
            else:
                logging.error(str(e))
                # Document feeder jammed
                raise
        end = time.time() - start
        if end < 2:
            logging.debug("Got backside")
            self.client_notify("backside")
        else:
            logging.debug("Page fed")
            self.client_notify("page fed")
        return self.dev.snap(True)

class Scanner(object):
    """SANE communication with scanner"""

    # Scanner default options
    defaults={
        'source':'ADF Duplex',
        'mode':'Color',
        'resolution':500,
        'ald':1,
        'swskip':15.0,
        'swcrop':0,
        'swdeskew':1,
        'swdespeck':2,
    }

    def __init__(self):
        super(Scanner, self).__init__()
        self.handle=None
        sane.init()
        self.get_device('FUJITSU')
        logging.debug('got scanning device')
        atexit.register(self.cleanup)
        self.output_dir = "" if len(sys.argv) < 2 else sys.argv[1]
        os.makedirs(self.output_dir,exist_ok=True)


    def get_device(self, manufac):
        devs = sane.get_devices()
        self.device = [x for x in devs if x[1] == manufac][0][0]

    def connect(self):
        self.handle = sane.open(self.device)
        logging.debug("Connected to {}".format(self.device))
        return self.handle

    def disconnect(self):
        if self.handle:
            logging.debug("Closing handle to {}".format(self.device))
            self.handle.close()
            self.handle=None

    def setopts(self, device, options):
        settings = {**self.defaults, **options}
        for opt,val in settings.items():
            logging.debug('setting printer option {}={}'.format(opt,val))
            setattr(device,opt,val)

    def removeFile(self, filename):
        try:
            os.remove(filename)
        except OSError:
            pass

    def scanwrite(self, feed, filename, client_notify):
        logging.info("creating {}".format(filename))
        pages=[]
        with TiffImagePlugin.AppendingTiffWriter(filename,new=True) as tiff:
            for i,page in enumerate(feed):
                logging.info('saving page {}...'.format(i+1))
                client_notify("PAGE {}".format(i+1))
                page.save(tiff)
                tiff.newFrame()
                pages.append(page)
                logging.debug("saved")
        return pages


    def perform_scan(self, device, client_notify):
        now = datetime.datetime.now()
        filename = "scan-{}.tiff".format(now.strftime("%Y%m%d%H%M%S_%f"))
        path = os.path.join(self.output_dir, filename)
        feeder = PageFeed(device, client_notify)
        try:
            pages = self.scanwrite(feeder, path, client_notify)
        except sane._sane.error as e:
            logging.error(str(e))
            logging.info("aborting scan, removing file")
            client_notify("error",str(e))
            self.removeFile(path)
            return False,[]
        else:
            if len(pages) == 0 or os.path.getsize(path) == 0:
                logging.debug("empty scan file. Removing")
                client_notify("empty scan")
                self.removeFile(path)
                return False,pages
            else:
                client_notify("complete")
                return True,pages

    # called as callback in Client socket processing
    def scan(self, options, client_notify=NOOP):
        logging.info('scan starting')
        device = self.connect()
        self.setopts(device, options)
        success,images = self.perform_scan(device, client_notify)
        logging.info('scan complete')
        self.disconnect()
        return success,images

    def cleanup(self):
        logging.info('cleaning up SANE')
        self.disconnect()
        sane.exit()

class Server(object):
    """Socket listener"""
    def __init__(self, port):
        super(Server, self).__init__()
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        bound=False
        while not bound:
            try:
                self.socket.bind(('',port))
            except OSError:
                logging.info("Socket in use, trying again")
                time.sleep(1)
            else:
                bound=True
        self.launch = NOOP
        logging.info('Server listening at port {}'.format(port))
        atexit.register(self.cleanup)

    def cleanup(self):
        logging.debug('Server closing socket')
        self.socket.close()

    def onconnect(self, cb):
        self.launch = cb

    def listen(self):
        self.socket.listen(5)
        while True:
            client = Client(*self.socket.accept())
            client.process(self.launch)
            client.cleanup()

def cleanup_at_exit():
    signal(SIGTERM, lambda signum, stack_frame: sys.exit(1))
    signal(SIGINT, lambda signum, stack_frame: sys.exit(1))

def main():
    cleanup_at_exit()
    scanner = Scanner()
    server = Server(5555)
    server.onconnect(scanner.scan)
    server.listen()

if __name__ == "__main__":
    main()
