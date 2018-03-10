#!/usr/bin/env python3
import socket
import atexit
import json
import logging

class Scanner(object):
	"""communication with scingest"""
	def __init__(self):
		super(Scanner, self).__init__()
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.connect(("192.168.1.28",5555))
		atexit.register(self.cleanup)

	def cleanup(self):
		self.socket.close()
	def run(self, options, process_msg):
		self._sendjson({"scan":True,"options":options})

		msg = self._get()
		while msg is not None:
			s = msg.decode("utf8")
			logging.info(s)
			exit_read_loop = process_msg(s)
			if exit_read_loop is not None:
				break
			msg = self._get()

		# None = broken pipe
		# True = successful scan
		# False = interrupted scan
		return None if msg is None else exit_read_loop


	def get_thumbnail(self, page):
		logging.debug('requesting thumbnail for page {}'.format(page))
		self._send(str(page))
		return self._get()

	def _sendb(self, b):
		msglen = len(b).to_bytes(4, byteorder='big')
		self.socket.send(msglen+b)
	def _send(self, s):
		self._sendb(s.encode('utf8'))
	def _sendjson(self, thing):
		self._send(json.dumps(thing))

	def _get(self):
		pkt_len = self.socket.recv(4)
		if pkt_len == b'':
			return None
		pkt_len = int.from_bytes(pkt_len, byteorder='big')
		nbytes=0
		chunks=[]
		while nbytes < pkt_len:
			chunk = self.socket.recv(min(pkt_len - nbytes, 2048))
			if chunk == b'':
				return None
			chunks.append(chunk)
			nbytes += len(chunk)
		return b''.join(chunks)
