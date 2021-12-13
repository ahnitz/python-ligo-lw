#!/usr/bin/env python3

import sys
from ligo.lw import ligolw
from ligo.lw import utils as ligolw_utils
import numpy
import time


def test_io_iteration_order():
	orig = numpy.arange(200**3, dtype = "double")
	orig.shape = (200,200,200)

	xmldoc = ligolw.Document()
	xmldoc.appendChild(ligolw.LIGO_LW()).appendChild(ligolw.Array.build("test", orig))

	start_write = time.perf_counter()
	ligolw_utils.write_filename(xmldoc, "big_array.xml.gz", compress = "gz", with_mv = False)
	end_write = time.perf_counter()
	print("writing took %g s" % (end_write - start_write))

	start_read = time.perf_counter()
	recov = ligolw.Array.get_array(ligolw_utils.load_filename("big_array.xml.gz", contenthandler = ligolw.LIGOLWContentHandler), "test").array
	end_read = time.perf_counter()
	print("reading took %g s" % (end_read - start_read))

	if not (recov == orig).all():
		raise ValueError("arrays are not the same")


if __name__ == '__main__':
	failures = False
	try:
		test_io_iteration_order()
	except ValueError:
		failures |= True
	sys.exit(bool(failures))
