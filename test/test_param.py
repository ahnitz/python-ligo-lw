#!/usr/bin/env python3

import doctest
import sys
from ligo.lw import param

if __name__ == '__main__':
	failures = doctest.testmod(param)[0]
	sys.exit(bool(failures))
