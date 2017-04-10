#!/usr/bin/env python

import doctest
import sys
from ligo.lw.utils import segments as ligolw_segments

if __name__ == '__main__':
	failures = doctest.testmod(ligolw_segments)[0]
	sys.exit(bool(failures))
