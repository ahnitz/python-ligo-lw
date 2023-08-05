#!/usr/bin/env python3

import doctest
import sys
from ligo.lw import ligolw

if __name__ == '__main__':
	failures = doctest.testmod(ligolw)[0]
	sys.exit(bool(failures))
