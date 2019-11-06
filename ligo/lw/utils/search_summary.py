# Copyright (C) 2012,2013,2015,2017,2019  Kipp Cannon
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.


#
# =============================================================================
#
#                                   Preamble
#
# =============================================================================
#


"""
A collection of utilities to assist applications in manipulating the
search_summary table in LIGO Light-Weight XML documents.
"""


from .. import __author__, __date__, __version__
from .. import lsctables


#
# =============================================================================
#
#                           Search Summary Metadata
#
# =============================================================================
#


def append_search_summary(xmldoc, process, shared_object = "standalone", lalwrapper_cvs_tag = "", lal_cvs_tag = "", comment = None, ifos = None, inseg = None, outseg = None, nevents = 0, nnodes = 1):
	"""
	Append search summary information associated with the given process
	to the search summary table in xmldoc.  Returns the newly-created
	search_summary table row.
	"""
	try:
		tbl = lsctables.SearchSummaryTable.get_table(xmldoc)
	except ValueError:
		tbl = xmldoc.childNodes[0].appendChild(lsctables.New(lsctables.SearchSummaryTable))
	tbl.append(tbl.RowType(
		process_id = process.process_id,
		shared_object = shared_object,
		lalwrapper_cvs_tag = lalwrapper_cvs_tag,
		lal_cvs_tag = lal_cvs_tag,
		comment = comment or process.comment,
		instruments = ifos if ifos is not None else process.instruments,
		in_segment = inseg,
		out_segment = outseg,
		nevents = nevents,
		nnodes = nnodes
	))
	return row


def segmentlistdict_fromsearchsummary_in(xmldoc, program = None):
	"""
	Convenience wrapper for a common case usage of the segmentlistdict
	class:  searches the process table in xmldoc for occurances of a
	program named program, then scans the search summary table for
	matching process IDs and constructs a segmentlistdict object from
	the in segments in those rows.

	Note:  the segmentlists in the segmentlistdict are not necessarily
	coalesced, they contain the segments as they appear in the
	search_summary table.
	"""
	return lsctables.SearchSummaryTable.get_table(xmldoc).get_in_segmentlistdict(program and lsctables.ProcessTable.get_table(xmldoc).get_ids_by_program(program))


def segmentlistdict_fromsearchsummary_out(xmldoc, program = None):
	"""
	Convenience wrapper for a common case usage of the segmentlistdict
	class:  searches the process table in xmldoc for occurances of a
	program named program, then scans the search summary table for
	matching process IDs and constructs a segmentlistdict object from
	the out segments in those rows.

	Note:  the segmentlists in the segmentlistdict are not necessarily
	coalesced, they contain the segments as they appear in the
	search_summary table.
	"""
	return lsctables.SearchSummaryTable.get_table(xmldoc).get_out_segmentlistdict(program and lsctables.ProcessTable.get_table(xmldoc).get_ids_by_program(program))
