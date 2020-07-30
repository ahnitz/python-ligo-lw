#!/usr/bin/env python

#import io
#import codecs
#class StringIO(io.StringIO):
#	# give io.StringIO an buffer attribute that mimics a binary file
#	@property
#	def buffer(self):
#		return self.detach()
#io.StringIO = StringIO
import doctest
import sys
from ligo.lw import utils

if __name__ == '__main__':
	failures = doctest.testmod(utils)[0]
	sys.exit(bool(failures))
