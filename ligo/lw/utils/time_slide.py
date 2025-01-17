# Copyright (C) 2006--2014  Kipp Cannon
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


from tqdm import tqdm
from .. import __author__, __date__, __version__
from .. import lsctables


#
# =============================================================================
#
#                                     I/O
#
# =============================================================================
#


def get_time_slide_id(xmldoc, time_slide, create_new = None, superset_ok = False, nonunique_ok = False):
	"""
	Return the time_slide_id corresponding to the offset vector
	described by time_slide, a dictionary of instrument/offset pairs.

	Example:

	>>> get_time_slide_id(xmldoc, {"H1": 0, "L1": 0})
	10

	This function is a wrapper around the .get_time_slide_id() method
	of the ligo.lw.lsctables.TimeSlideTable class.  See the
	documentation for that class for the meaning of the create_new,
	superset_ok and nonunique_ok keyword arguments.

	This function requires the document to contain exactly one
	time_slide table.  If the document does not contain exactly one
	time_slide table then ValueError is raised, unless the optional
	create_new argument is not None.  In that case a new table is
	created.  This effect of the create_new argument is in addition to
	the effects described by the TimeSlideTable class.
	"""
	tisitable = lsctables.TimeSlideTable.ensure_exists(xmldoc, create_new = create_new)
	tisitable.sync_next_id()
	return tisitable.get_time_slide_id(time_slide, create_new = create_new, superset_ok = superset_ok, nonunique_ok = nonunique_ok)


#
# =============================================================================
#
#                            Time Slide Comparison
#
# =============================================================================
#


def time_slides_vacuum(time_slides, verbose = False):
	"""
	Given a dictionary mapping time slide IDs to instrument-->offset
	mappings, for example as returned by the as_dict() method of the
	TimeSlideTable class in ligo.lw.lsctables, construct and return a
	mapping indicating time slide equivalences.  This can be used to
	delete redundant time slides from a time slide table, and then also
	used via the applyKeyMapping() method of ligo.lw.table.Table
	instances to update cross references (for example in the
	coinc_event table).

	Example:

	>>> slides = {0: {"H1": 0, "H2": 0}, 1: {"H1": 10, "H2": 10}, 2: {"H1": 0, "H2": 10}}
	>>> time_slides_vacuum(slides)
	{1: 0}

	indicating that time slide ID 1 describes a time slide that is
	equivalent to time slide ID 0.  The calling code could use this
	information to delete time slide ID 1 from the time_slide table,
	and replace references to that ID in other tables with references
	to time slide ID 0.
	"""
	# convert offsets to deltas
	time_slides = dict((time_slide_id, offsetvect.deltas) for time_slide_id, offsetvect in time_slides.items())
	with tqdm(total=len(time_slides), disable=not verbose) as progressbar:
		# old --> new mapping
		mapping = {}
		# while there are time slide offset dictionaries remaining
		while time_slides:
			# pick an ID/offset dictionary pair at random
			id1, deltas1 = time_slides.popitem()
			# for every other ID/offset dictionary pair in the time
			# slides
			ids_to_delete = []
			for id2, deltas2 in time_slides.items():
				# if the relative offset dictionaries are
				# equivalent record in the old --> new mapping
				if deltas2 == deltas1:
					mapping[id2] = id1
					ids_to_delete.append(id2)
			for id2 in ids_to_delete:
				time_slides.pop(id2)
			# number of offset vectors removed from time_slides
			# in this iteration
			progressbar.update(1 + len(ids_to_delete))
	# done
	return mapping


def time_slide_list_merge(slides1, slides2):
	"""
	Merges two lists of offset dictionaries into a single list with
	no duplicate (equivalent) time slides.
	"""
	deltas1 = set(frozenset(offsetvect1.deltas.items()) for offsetvect1 in slides1)
	return slides1 + [offsetvect2 for offsetvect2 in slides2 if frozenset(offsetvect2.deltas.items()) not in deltas1]
