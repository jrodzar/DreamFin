# -*- coding: utf-8 -*-
"""Tiny in-process mock of an Emby/Jellyfin server for offline tests.

Serves canned JSON per path, records every request (method, path,
query, headers and decoded JSON body) and supports the Emby paging
protocol (``StartIndex``/``Limit`` query parameters,
``TotalRecordCount`` in the envelope) plus HTTP redirects and canned
error statuses.

Works on Python 2.7 and Python 3.x.
"""

import json
import threading

try:
	from http.server import BaseHTTPRequestHandler, HTTPServer
	from socketserver import ThreadingMixIn
except ImportError:  # Python 2
	from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
	from SocketServer import ThreadingMixIn

try:
	from urllib.parse import urlparse, parse_qs
except ImportError:  # Python 2
	from urlparse import urlparse, parse_qs


class _ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
	# keep-alive clients must not block other connections
	daemon_threads = True
	allow_reuse_address = True

	def handle_error(self, request, client_address):
		# abruptly closed keep-alive connections are expected
		pass


class _Handler(BaseHTTPRequestHandler):
	protocol_version = "HTTP/1.1"

	def log_message(self, fmt, *args):  # silence default stderr logging
		pass

	def do_GET(self):
		self._serve("GET")

	def do_POST(self):
		self._serve("POST")

	def do_PUT(self):
		self._serve("PUT")

	def do_DELETE(self):
		self._serve("DELETE")

	def _serve(self, method):
		parsed = urlparse(self.path)
		headers = {}
		for key in self.headers.keys():
			headers[key.lower()] = self.headers[key]

		bodyBytes = b""
		length = headers.get("content-length")
		if length:
			bodyBytes = self.rfile.read(int(length))

		bodyJson = None
		if bodyBytes:
			try:
				bodyJson = json.loads(bodyBytes.decode("utf-8"))
			except (ValueError, UnicodeDecodeError):
				pass

		record = {
			"method": method,
			"path": parsed.path,
			"query": parse_qs(parsed.query),
			"raw": self.path,
			"headers": headers,
			"body": bodyJson,
			"body_raw": bodyBytes,
		}
		self.server.requests.append(record)

		route = self._pick_route(method, parsed.path)
		if route is None:
			self._respond(404, "text/plain", b"not found")
			return

		rtype = route["type"]
		if rtype == "json":
			payload = route["body"]
			if callable(payload):
				payload = payload(record)
			self._respond(200, "application/json;charset=utf-8", _encode_json(payload))

		elif rtype == "raw":
			self._respond(200, route["content_type"], _encode(route["body"]))

		elif rtype == "redirect":
			body = b"moved"
			self.send_response(route["status"])
			self.send_header("Location", route["location"])
			self.send_header("Content-Length", str(len(body)))
			self.end_headers()
			self.wfile.write(body)

		elif rtype == "paged":
			self._respond_paged(route, record)

		elif rtype == "error":
			self._respond(route["status"], "text/plain", _encode(route.get("body", "error")))

		else:
			self._respond(500, "text/plain", b"bad route")

	def _pick_route(self, method, path):
		"""Routes live in a stack per key: the top entry is served and,
		when registered with a limited ``times`` budget, popped once
		exhausted so the next entry underneath takes over."""
		for key in ((method, path), path):
			stack = self.server.routes.get(key)
			if not stack:
				continue
			route = stack[-1]
			times = route.get("times")
			if times is not None:
				route["times"] = times - 1
				if route["times"] <= 0:
					stack.pop()
			return route
		return None

	def _respond_paged(self, route, record):
		items = route["items"]
		total = len(items)

		start = _int_param(record, "StartIndex", 0)
		limit = _int_param(record, "Limit", total)

		window = items[start:start + limit]
		envelope = dict(route.get("extra", {}))
		envelope["Items"] = window
		envelope["TotalRecordCount"] = total
		envelope["StartIndex"] = start
		self._respond(200, "application/json;charset=utf-8", _encode_json(envelope))

	def _respond(self, status, content_type, body):
		self.send_response(status)
		self.send_header("Content-Type", content_type)
		self.send_header("Content-Length", str(len(body)))
		self.end_headers()
		self.wfile.write(body)


def _encode(body):
	if isinstance(body, bytes):
		return body
	return body.encode("utf-8")


def _encode_json(payload):
	if isinstance(payload, bytes):
		return payload
	if isinstance(payload, str):
		return payload.encode("utf-8")
	return json.dumps(payload).encode("utf-8")


def _int_param(record, name, default):
	values = record["query"].get(name)
	if not values:
		return default
	try:
		return int(values[0])
	except (TypeError, ValueError):
		return default


class MockEmby(object):
	"""Mock Emby/Jellyfin server bound to 127.0.0.1 on an ephemeral port."""

	def __init__(self):
		self.httpd = _ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
		self.httpd.routes = {}
		self.httpd.requests = []
		self.port = self.httpd.server_address[1]
		self.host = "127.0.0.1"
		self._thread = threading.Thread(target=self.httpd.serve_forever)
		self._thread.daemon = True

	# -- lifecycle -----------------------------------------------------------
	def start(self):
		self._thread.start()
		return self

	def stop(self):
		self.httpd.shutdown()
		self.httpd.server_close()

	# -- route registration ---------------------------------------------------
	def _register(self, key, route, push):
		stack = self.httpd.routes.setdefault(key, [])
		if push:
			stack.append(route)
		else:
			del stack[:]
			stack.append(route)

	def add_json(self, path, body, method=None, times=None):
		"""body: dict/list, pre-encoded str/bytes, or callable(record)."""
		key = (method, path) if method else path
		self._register(key, {"type": "json", "body": body, "times": times}, push=times is not None)

	def add_paged(self, path, items, extra=None):
		"""Serve an ``{Items, TotalRecordCount, StartIndex}`` envelope
		honouring the StartIndex/Limit query parameters."""
		self._register(path, {"type": "paged", "items": list(items), "extra": extra or {}}, push=False)

	def add_raw(self, path, content_type, body):
		self._register(path, {"type": "raw", "content_type": content_type, "body": body}, push=False)

	def add_redirect(self, path, location, status=302):
		self._register(path, {"type": "redirect", "status": status, "location": location}, push=False)

	def add_error(self, path, status, body="error", method=None, times=None):
		"""With times=N the error is served N times, then the previously
		registered route for the same path takes over again."""
		key = (method, path) if method else path
		self._register(key, {"type": "error", "status": status, "body": body, "times": times}, push=times is not None)

	# -- inspection ------------------------------------------------------------
	@property
	def address(self):
		return "%s:%d" % (self.host, self.port)

	@property
	def requests(self):
		return self.httpd.requests

	def requests_for(self, path):
		return [r for r in self.httpd.requests if r["path"] == path]

	def reset_requests(self):
		del self.httpd.requests[:]
