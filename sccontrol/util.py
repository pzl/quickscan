#!/usr/bin/env python3
import os
from PIL import ImageFont

def is_pi():
	return os.uname().machine[:3] == 'arm'

def circle(x,y,r):
	return (x-r,y-r,x+r,y+r)

def document(d,x,y,n,backside=False,active=False):
	ratio=(8.5,11)
	scale=1.5

	w=ratio[0]*scale
	h=ratio[1]*scale
	#d.rectangle((x,y,x+w,y+h),outline="white")
	if backside:
		pts = (
			x+w/3,y,
			x+w,y,
			x+w,y+h,
			x,y+h,
			x,y+h/4
		)
	else:
		pts = (
			x,y,
			x+w*2/3,y,
			x+w*2/3,y+h/4,
			x+w,y+h/4,
			x+w,y+h,
			x,y+h,
		)
		d.line(( x+w*2/3,y,  x+w,y+h/4 ),fill="white",width=1)

	if active:
		d.polygon(pts, fill="white")
	else:
		d.polygon(pts, outline="white")
	d.text((x+w/2,y+h/2),str(n),fill="black" if active else "white",font=loadfont("tiny.ttf",6))

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
