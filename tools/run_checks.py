# -*- coding: utf-8 -*-
"""Offline gate for the dual py2/py3 requirement.

1. Byte-compiles every plugin module with the running interpreter.
2. Scans every plugin module for syntax that Python 2.7
   (OpenATV 6.4) cannot parse: f-strings, walrus, async/await,
   argument-less super(), nonlocal, ``yield from`` and annotations.
3. Verifies every path referenced from the skins exists in the tree
   (tools/check_skin_paths.py).
4. Refuses a CR in any text file the IPK would ship: git cannot show a
   CRLF rewrite of the working tree here, and the IPK is built from the
   working tree.

Run with:  py -3 tools/run_checks.py
"""

from __future__ import print_function

import os
import py_compile
import re
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_ipk  # noqa: E402
import check_skin_paths  # noqa: E402

PY3_ONLY_PATTERNS = [
	(re.compile(r"(?<![\w.\"'])[rbuRBU]{0,2}[fF][rbuRBU]{0,2}[\"']"), "f-string literal"),
	(re.compile(r":="), "walrus operator"),
	(re.compile(r"\basync\s+def\b"), "async def"),
	(re.compile(r"\bawait\s"), "await"),
	(re.compile(r"\bnonlocal\b"), "nonlocal"),
	(re.compile(r"\byield\s+from\b"), "yield from"),
	(re.compile(r"\bsuper\(\)"), "argument-less super()"),
	(re.compile(r"^\s*def\s+\w+\s*\([^)]*\)\s*->"), "return annotation"),
]


def iter_python_files():
	for base in ("src", "tests", "tools"):
		for root, dirs, files in os.walk(os.path.join(REPO_ROOT, base)):
			dirs[:] = [d for d in dirs if d != "__pycache__"]
			for name in sorted(files):
				if name.endswith(".py"):
					yield os.path.join(root, name)


def strip_comments_and_strings(line):
	"""Very light scrub so patterns don't fire inside comments."""
	hashPos = line.find("#")
	if hashPos != -1:
		line = line[:hashPos]
	return line


def check_compile():
	failures = []
	tmpdir = tempfile.mkdtemp(prefix="dreamfin-compile-")
	count = 0
	for path in iter_python_files():
		count += 1
		target = os.path.join(tmpdir, "out%d.pyc" % count)
		try:
			py_compile.compile(path, cfile=target, doraise=True)
		except py_compile.PyCompileError as error:
			failures.append("%s: %s" % (path, error.msg))
		try:
			if os.path.exists(target):
				os.remove(target)
		except OSError:
			pass
	try:
		os.rmdir(tmpdir)
	except OSError:
		pass
	return count, failures


def iter_py2_guarded_files():
	"""Every plugin module must stay Python 2.7 (OpenATV 6.4) compatible."""
	srcRoot = os.path.join(REPO_ROOT, "src")
	for root, dirs, files in os.walk(srcRoot):
		dirs[:] = [d for d in dirs if d != "__pycache__"]
		for name in sorted(files):
			if name.endswith(".py"):
				path = os.path.join(root, name)
				yield path, os.path.relpath(path, REPO_ROOT).replace(os.sep, "/")


def check_py2_syntax():
	failures = []
	for path, relative in iter_py2_guarded_files():
		fd = open(path, "rb")
		try:
			lines = fd.read().decode("utf-8", "replace").splitlines()
		finally:
			fd.close()
		for number, line in enumerate(lines, 1):
			scrubbed = strip_comments_and_strings(line)
			for pattern, label in PY3_ONLY_PATTERNS:
				if pattern.search(scrubbed):
					failures.append("%s:%d: %s -> %s" % (relative, number, label, line.strip()))
	return failures


def check_packaged_line_endings():
	"""No text file the IPK ships may carry a CR.

	git is no help here: with ``* text=auto eol=lf`` a whole-file CRLF
	rewrite leaves ``git diff`` EMPTY (``git status`` only says M) and
	``git add`` silently turns it back into LF - but build_ipk.py packages
	the working tree, not git. So this walks build_ipk.iter_data_members(),
	the very bytes the IPK would carry. Binary members (png, ttf, the
	compiled .mo) are told apart by a NUL byte, as git does; the maintainer
	scripts are normalised by build_ipk.build_control_members, and parse_po
	strips line endings from the .po sources.
	"""
	failures = []
	seen = {}
	for arcname, payload, mode in build_ipk.iter_data_members():
		if b"\x00" in payload[:8000]:
			continue
		extension = os.path.splitext(arcname)[1] or "(none)"
		seen[extension] = seen.get(extension, 0) + 1
		count = payload.count(b"\r")
		if count:
			failures.append("%s: %d CR" % (arcname, count))
	# the IPK always ships python modules and skin xml: seeing none of
	# either means the walk broke, and a broken walk must not pass as clean
	for extension in (".py", ".xml"):
		if not seen.get(extension):
			failures.append("no packaged %s file examined: the walk is broken" % extension)
	return sum(seen.values()), failures


def main():
	count, compileFailures = check_compile()
	print("byte-compiled %d files with %s" % (count, sys.version.split()[0]))

	py2Failures = check_py2_syntax()

	textCount, crFailures = check_packaged_line_endings()
	print("checked %d packaged text files for CR" % textCount)

	skinFailure = check_skin_paths.main([]) != 0

	ok = True
	if compileFailures:
		ok = False
		print("\nCOMPILE ERRORS:")
		for failure in compileFailures:
			print("  " + failure)

	if py2Failures:
		ok = False
		print("\nPY3-ONLY SYNTAX IN PY2-GUARDED FILES:")
		for failure in py2Failures:
			print("  " + failure)

	if crFailures:
		ok = False
		print("\nCR IN PACKAGED TEXT FILES (git diff does not show these):")
		for failure in crFailures:
			print("  " + failure)

	if skinFailure:
		ok = False

	if ok:
		print("all checks passed")
		return 0
	return 1


if __name__ == "__main__":
	sys.exit(main())
