#!/usr/bin/env python3
import os
from PIL import ImageFont

def is_pi():
	return os.uname().machine[:3] == 'arm'

def circle(x,y,r):
	return (x-r,y-r,x+r,y+r)

def document(d,x,y,n,backside=False):
	ratio=(8.5,11)
	scale=1.5
	#d.rectangle((x,y,x+ratio[0]*scale,y+ratio[1]*scale),outline="white")
	if backside:
		d.polygon(
			(
				x+(ratio[0]*scale)/3,y,
				x+ratio[0]*scale,y,
				x+ratio[0]*scale,y+ratio[1]*scale,
				x,y+ratio[1]*scale,
				x,y+(ratio[1]*scale)/4
			),
			outline="white"
		)
	else:
		d.polygon(
			(
				x,y,
				x+(ratio[0]*scale)*2/3,y,
				x+(ratio[0]*scale)*2/3,y+(ratio[1]*scale)/4,
				x+ratio[0]*scale,y+(ratio[1]*scale)/4,
				x+ratio[0]*scale,y+ratio[1]*scale,
				x,y+ratio[1]*scale,
			),
			outline="white"
		)
		d.line(( x+(ratio[0]*scale)*2/3,y,  x+ratio[0]*scale,y+(ratio[1]*scale)/4 ),fill="white",width=1)
	d.text((x+(ratio[0]*scale)/2,y+(ratio[1]*scale)/2),str(n),fill="white",font=loadfont("tiny.ttf",6))

def loadfont(name, size=12):
		fontp = os.path.abspath(os.path.join(
			os.path.dirname(__file__),
			'fonts', name))
		return ImageFont.truetype(fontp, size)

class screen_timeout(object):
	"""simple context manager for controlling a screen sleep time"""
	def __init__(self, screen, t=5):
		super(screen_timeout, self).__init__()
		self.screen = screen
		self.t=t
	def __enter__(self):
		pass
		self.screen.activate()
	def __exit__(self, *_):
		#self.screen.activate() # activate after drawing has finished
		self.screen.sleep_timeout(self.t)
