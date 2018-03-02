#!/usr/bin/env python3

import sane
from PIL import TiffImagePlugin
import logging
import socket
import json
from signal import signal, SIGTERM, SIGINT
import atexit
import sys

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

logging.basicConfig(level=logging.DEBUG)

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
        return json.loads(msg.decode('utf8'))

    def process(self, cb):
        # client should contact us first with options
        opts = self._get_command()
        cb(opts)


class PageFeed(object):
    """Page iterator for ADF feed since python-sane doesn't do it right for python3"""
    def __init__(self, dev):
        super(PageFeed, self).__init__()
        self.dev = dev
    def __iter__(self):
        return self
    def __del__(self):
        self.dev.cancel()
    def __next__(self):
        try:
            self.dev.start()
        except Exception as e:
            if str(e) == 'Document feeder out of documents':
                raise StopIteration
            else:
                raise
        return self.dev.snap(True)

class Scanner(object):
    """SANE communication with scanner"""

    # Scanner default options
    defaults={
        'source':'ADF Duplex',
        'mode':'Color',
        'resolution':300,
        'ald':1,
        'swskip':15.0,
        'swcrop':1,
        'swdeskew':1,
        'swdespeck':1,
    }

    def __init__(self):
        super(Scanner, self).__init__()
        self.handle=None
        sane.init()
        self.get_device('FUJITSU')
        logging.debug('got scanning device')
        atexit.register(self.cleanup)

    def get_device(self, manufac):
        devs = sane.get_devices()
        self.device = [x for x in devs if x[1] == manufac][0][0]

    def connect(self):
        self.handle = sane.open(self.device)
        logging.debug("Connected to {}".format(self.device))

    def disconnect(self):
        if self.handle:
            logging.debug("Closing handle to {}".format(self.device))
            self.handle.close()
            self.handle=None

    def setopts(self, device, options):
        settings = {**self.defaults, **options}
        for opt,val in settings:
            setattr(device,opt,val)

    def scanwrite(self, feed, filename):
        with TiffImagePlugin.AppendingTiffWriter(filename) as tiff:
            for i,page in enumerate(feed):
                logging.info('reading page {}...'.format(i))
                page.save(tiff)
                tiff.newFrame

    # called as callback in Client socket processing
    def scan(self, options):
        logging.info('scan starting')
        device = self.connect()
        self.setopts(device, options)
        pages = PageFeed(device)
        self.scanwrite(pages, "out.tiff")
        logging.info('scan complete')
        self.disconnect()

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
        self.socket.bind(('',port))
        self.launch = lambda x: pass
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
            client.process(cb)

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
