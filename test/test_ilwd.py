#!/usr/bin/env python

import doctest
import sys
from ligo.lw import _ilwd
from ligo.lw import ilwd

if __name__ == "main":
	failures = doctest.testmod(_ilwd)[0]
	failures += doctest.testmod(ilwd)[0]

	sys.exit(bool(failures))
