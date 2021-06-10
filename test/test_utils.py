#!/usr/bin/env python3

import doctest
import sys
from ligo.lw import utils as ligolw_utils

if __name__ == '__main__':
	failures = doctest.testmod(ligolw_utils)[0]
	sys.exit(bool(failures))
