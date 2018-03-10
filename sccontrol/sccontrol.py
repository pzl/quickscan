#!/usr/bin/env python3
import sys
from signal import signal, SIGTERM, SIGINT
import time
import logging
from util import is_pi
from scan import Scanner
from ui import Button_Interface, Keys_Interface
from display import MenuPage, SettingPage, ProgressPage, Screen, LCD, Mock_LCD

logging.basicConfig(level=logging.DEBUG,format="%(asctime)s %(levelname)7s : %(message)s")

class Setting(object):
	"""Settings collection object"""
	def __init__(self, name, values, current=None):
		super(Setting, self).__init__()
		if type(name) is dict:
			self.name = list(name.keys())[0]
			self.setting_name = name[self.name]
		else:
			self.name=name
			self.setting_name=name
		self.values = [ list(x.keys())[0] if type(x) is dict else x for x in values ]
		self.setting_values = [ list(x.values())[0] if type(x) is dict else x for x in values ]
		self.current = current if current else values[0]
	def __str__(self):
		return "{}: {}".format(self.name, self.current)
	def __repr__(self):
		return self.__str__()
	def index(self):
		return self.values.index(self.current)

class Menu(object):
	"""Main menu"""
	def __init__(self):
		super(Menu, self).__init__()
		self.settings = []
		self.settings.append(Setting({"Mode":"mode"},("Color","Gray",{"B/W":"Lineart"})))
		self.settings.append(Setting({"DPI":"resolution"},list(range(50,601,50)),500))
		self.settings.append(Setting({"Sides":"source"},({1:"ADF Front"},{2:"ADF Duplex"}),2))
		self.main = MenuPage("Main Menu", self.settings)
		self.page = self.main

	def up(self):
		self.page.up()
	def down(self):
		self.page.down()
	def enter(self):
		if self.page == self.main:
			setting = self.settings[self.page.highlighted]
			self.page = SettingPage(setting)
		else:
			self.page.select()
			self.page = self.main
	def draw(self, canvas, device):
		self.page.draw(canvas, device)


class IO_Mgr(object):
	"""Manager for a collection of buttons"""
	def __init__(self, interface, screen, menu, lcd):
		super(IO_Mgr, self).__init__()
		self.buttons=[]
		self.interface = interface
		self.screen=screen
		self.menu = menu
		self.lcd = lcd

	# called as callback from server scanner.run, server comms
	# return true to exit scanner running
	def handle_status(self, progress):
		def response(msg):
			msg,*args = msg.split(":",maxsplit=1)
			msg = msg.strip()
			if msg == "error":
				self.screen.draw_err(*args)
				return False # @todo: what if there are further status messages?
			elif msg == "complete":
				progress.complete = True
				return True # break read-cycle to handle scan completion
			elif msg == "empty scan":
				self.screen.draw_empty()
				return False
			else:
				self.screen.draw_progress(progress, msg)
		return response


	def listen(self, handler=None):
		if handler is None:
			handler = self.menu_button_handler
		while True:
			try:
				self.interface.listen(handler)
			except StopIteration:
				break

	def scan(self):
		try:
			scanner = Scanner()
		except ConnectionRefusedError:
			logging.debug("could not connect to scingest")
			self.screen.draw_err("couldn't find server")
			time.sleep(2)
			self.screen.draw_menu(self.menu)
			return

		settings = {}
		for s in self.menu.settings:
			logging.debug("setting {} = {}".format(s.setting_name,s.setting_values[s.index()]))
			settings[s.setting_name] = s.setting_values[s.index()]

		progress = ProgressPage()
		success = scanner.run(settings,self.handle_status(progress))

		if success:
			self.screen.draw_progress(progress,"")
			self.listen(self.progress_button_handler(scanner,progress))
		
		self.listen(self.acknowledge_button_handler)

		scanner.cleanup()
		self.screen.draw_menu(self.menu)

	def progress_button_handler(self,scanner,progress):
		def fn(action):
			if action == 'up':
				progress.up()
				self.screen.draw_progress(progress,"")
			elif action == 'down':
				progress.down()
				self.screen.draw_progress(progress,"")
			elif action == 'enter':
				data = scanner.get_thumbnail(progress.selected)
				self.lcd.show(data)
			elif action == 'scan':
				self.screen.draw_complete()
				raise StopIteration
		return fn

	def menu_button_handler(self,action):
		if self.screen.is_asleep():
			self.screen.on()
			return
		if action == 'up':
			self.menu.up()
			self.screen.draw_menu(self.menu)
		elif action == 'down':
			self.menu.down()
			self.screen.draw_menu(self.menu)
		elif action == 'enter':
			self.menu.enter()
			self.screen.draw_menu(self.menu)
		elif action == 'scan':
			self.screen.draw_scan()
			self.scan()


	def acknowledge_button_handler(self,action):
		raise StopIteration

def cleanup_at_exit():
	signal(SIGTERM, lambda signum, stack_frame: sys.exit(1))
	signal(SIGINT, lambda signum, stack_frame: sys.exit(1))

def main():
	cleanup_at_exit()
	pins=(11,13,15,16)
	menu = Menu()
	screen = Screen(menu)
	interface = Button_Interface(pins) if is_pi() else Keys_Interface()
	lcd = LCD() if is_pi() else Mock_LCD()
	io = IO_Mgr(interface, screen, menu, lcd)
	io.listen()

if __name__ == "__main__":
	main()