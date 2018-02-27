Quickscan
==========

**quickscan** is a collection of services to add one-button scan operation to my scanner (Fujitsu S1500M).

The scanner itself _has_ a button on it, that _may_ work with SANE button daemons like [scanbd](https://sourceforge.net/projects/scanbd/), [scanbuttond](http://scanbuttond.sourceforge.net/), or others. But they involve odd SANE configurations to handle polling the button, and separate configs for performing the scan. 

Instead, I went the crazy route of adding a button to a Raspberry Pi, and having the Pi trigger the scan function. 

![program block diagram](quickscan.png)

sccontrol
---------

**sccontrol** is the main menu/button daemon. I have connected one of the various cheap OLED I2C displays to the pi, and have status information printed via the excellent [`luma.oled`](https://github.com/rm-hull/luma.oled) library. This runs on the Pi in order to use I2C to communicate with the display, and GPIO buttons.

scingest
---------

**scingest** is the kick-off logic for performing a SANE scan. This _may_ run on the same host as `sccontrol`, but for performance reasons I run this on a quicker machine. This is a python script that awaits commands from `sccontrol`, triggers scans via [python-sane](https://pypi.python.org/pypi/python-sane/2.8.2), saves the returned images, and forwards any SANE output to `sccontrol` to display.


The third piece to all this is a running SANE server for `scingest` to talk to. Can be completely standard setup for that.