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
from ligo.lw import utils as ligolw_utils

if __name__ == '__main__':
	failures = doctest.testmod(ligolw_utils)[0]
	sys.exit(bool(failures))
