#!/usr/bin/env python3

import doctest
import sys
from ligo.lw import lsctables

if __name__ == '__main__':
	failures = doctest.testmod(lsctables)[0]
	sys.exit(bool(failures))
