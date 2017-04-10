#!/usr/bin/env python

import doctest
import sys
from ligo.lw import table

if __name__ == '__main__':
	failures = doctest.testmod(table)[0]
	sys.exit(bool(failures))
