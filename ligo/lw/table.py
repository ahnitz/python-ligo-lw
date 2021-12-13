# Copyright (C) 2006--2021  Kipp Cannon
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 3 of the License, or (at your
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
Deprecated.  Do not use.  The Column and Table classes in ligolw now
implement the features previously found here.
"""

import warnings

warnings.warn("ligo.lw.table module is deprecated.  the features previously implemented by the Column and Table classes in this module are now implemented natively by the classes in the ligo.lw.ligolw module proper.  this module will be removed in the next release.")


from . import __author__, __date__, __version__
from . import ligolw


#
# =============================================================================
#
#                                  Utilities
#
# =============================================================================
#


def reassign_ids(elem):
	"""
	Recurses over all Table elements below elem whose next_id
	attributes are not None, and uses the .get_next_id() method of each
	of those Tables to generate and assign new IDs to their rows.  The
	modifications are recorded, and finally all ID attributes in all
	rows of all tables are updated to fix cross references to the
	modified IDs.

	This function is used by ligolw_add to assign new IDs to rows when
	merging documents in order to make sure there are no ID collisions.
	Using this function in this way requires the .get_next_id() methods
	of all Table elements to yield unused IDs, otherwise collisions
	will result anyway.  See the .sync_next_id() method of the Table
	class for a way to initialize the .next_id attributes so that
	collisions will not occur.

	Example:

	>>> from ligo.lw import ligolw
	>>> from ligo.lw import lsctables
	>>> xmldoc = ligolw.Document()
	>>> xmldoc.appendChild(ligolw.LIGO_LW()).appendChild(lsctables.New(lsctables.SnglInspiralTable))
	[]
	>>> reassign_ids(xmldoc)
	"""
	mapping = {}
	for tbl in elem.getElementsByTagName(ligolw.Table.tagName):
		if tbl.next_id is not None:
			tbl.updateKeyMapping(mapping)
	for tbl in elem.getElementsByTagName(ligolw.Table.tagName):
		tbl.applyKeyMapping(mapping)


#
# =============================================================================
#
#                               Content Handler
#
# =============================================================================
#


def use_in(ContentHandler):
	warnings.warn("ligo.lw.table module is deprecated.  the features previously implemented by the Column and Table classes in this module are now implemented natively by the classes in the ligo.lw.ligolw module proper.  this module will be removed in the next release.")
	return ContentHandler
