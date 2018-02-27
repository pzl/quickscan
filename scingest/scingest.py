#!/usr/bin/env python3

import sane
from PIL import TiffImagePlugin

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

class Feed(object):
    """Page iterator for ADF feed since python-sane doesn't do it right for python3"""
    def __init__(self, dev):
        super(Feed, self).__init__()
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

def get_fujitsu():
    devs = sane.get_devices()
    return sane.open(next(x for x in devs if x[1] == 'FUJITSU')[0])

def set_defaults(fj):
    fj.source='ADF Duplex'
    fj.mode='Color'
    fj.resolution=300
    fj.ald=1
    fj.swskip=15.0
    fj.swcrop=1
    fj.swdeskew=1
    fj.swdespeck=1


def scan(device):
    """ This was a bit unreliable, and giving 0 when paper was fully loaded
    if not device.page_loaded:
        print("no pages")
        return
    """
    feed = Feed(device)
    with TiffImagePlugin.AppendingTiffWriter("out.tiff") as tiff:
        for i,page in enumerate(feed):
            print('reading page {}...'.format(i))
            page.save(tiff)
            tiff.newFrame()
    print("done")


def main():
    sane.init()
    devs = sane.get_devices()
    fj = get_fujitsu()
    set_defaults(fj)
    scan(fj)
    fj.close()

if __name__ == "__main__":
    main()
