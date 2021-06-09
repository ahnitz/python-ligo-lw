#!/usr/bin/env python3

import doctest
import sys
from ligo.lw.utils import process as ligolw_process

if __name__ == '__main__':
	failures = doctest.testmod(ligolw_process)[0]
	sys.exit(bool(failures))
