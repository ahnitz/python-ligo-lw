#!/usr/bin/env python

import doctest
import sys
from ligo.lw import tokenizer

if __name__ == '__main__':
	failures = doctest.testmod(tokenizer)[0]
	sys.exit(bool(failures))
