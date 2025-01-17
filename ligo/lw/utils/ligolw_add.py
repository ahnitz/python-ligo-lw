# Copyright (C) 2006-2014,2016-2018,2020,2021  Kipp Cannon
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
Add (merge) LIGO LW XML files containing LSC tables.
"""


import os
import urllib.parse
import sys


from tqdm import tqdm
from .. import __author__, __date__, __version__
from .. import ligolw
from .. import lsctables
from .. import utils as ligolw_utils


#
# =============================================================================
#
#                                    Input
#
# =============================================================================
#


def url2path(url):
	"""
	If url identifies a file on the local host, return the path to the
	file otherwise raise ValueError.
	"""
	scheme, host, path, nul, nul, nul = urllib.parse.urlparse(url)
	if scheme.lower() in ("", "file") and host.lower() in ("", "localhost"):
		return path
	raise ValueError(url)


def remove_input(urls, preserves, verbose = False):
	"""
	Attempt to delete all files identified by the URLs in urls except
	any that are the same as the files in the preserves list.
	"""
	for path in map(url2path, urls):
		if any(os.path.samefile(path, preserve) for preserve in preserves):
			continue
		if verbose:
			sys.stderr.write("removing \"%s\" ...\n" % path)
		try:
			os.remove(path)
		except:
			pass


#
# =============================================================================
#
#                                Document Merge
#
# =============================================================================
#


def reassign_ids(doc, verbose = False):
	"""
	Assign new IDs to all rows in all LSC tables in doc so that there
	are no collisions when the LIGO_LW elements are merged.
	"""
	# Can't simply run reassign_ids() on doc because we need to
	# construct a fresh old --> new mapping within each LIGO_LW block.
	for elem in tqdm(doc.childNodes, desc='reassigning row IDs', disable=not verbose):
		if elem.tagName == ligolw.LIGO_LW.tagName:
			elem.reassign_table_row_ids()
	return doc


def merge_ligolws(elem):
	"""
	Merge all LIGO_LW elements that are immediate children of elem by
	appending their children to the first.
	"""
	ligolws = [child for child in elem.childNodes if child.tagName == ligolw.LIGO_LW.tagName]
	if ligolws:
		dest = ligolws.pop(0)
		for src in ligolws:
			# copy children;  LIGO_LW elements have no attributes
			for elem in src.childNodes:
				dest.appendChild(elem)
			# unlink from parent
			if src.parentNode is not None:
				src.parentNode.removeChild(src)
	return elem


def compare_table_cols(a, b):
	"""
	Return False if the two tables a and b have the same columns
	(ignoring order) according to LIGO LW name conventions, return True
	otherwise.
	"""
	return {(col.Name, col.Type) for col in a.getElementsByTagName(ligolw.Column.tagName)} != {(col.Name, col.Type) for col in b.getElementsByTagName(ligolw.Column.tagName)}


def merge_compatible_tables(elem):
	"""
	Below the given element, find all Tables whose structure is
	described in lsctables, and merge compatible ones of like type.
	That is, merge all SnglBurstTables that have the same columns into
	a single table, etc..
	"""
	for name in ligolw.Table.TableByName.keys():
		tables = ligolw.Table.getTablesByName(elem, name)
		if tables:
			dest = tables.pop(0)
			for src in tables:
				if src.Name != dest.Name:
					# src and dest have different names
					continue
				# src and dest have the same names
				if compare_table_cols(dest, src):
					# but they have different columns
					raise ValueError("document contains %s tables with incompatible columns" % dest.Name)
				# and the have the same columns
				# copy src rows to dest
				for row in src:
					dest.append(row)
				# unlink src from parent
				if src.parentNode is not None:
					src.parentNode.removeChild(src)
				src.unlink()
	return elem


#
# =============================================================================
#
#                                 Library API
#
# =============================================================================
#


# FIXME: compatibility stub.  delete after initial 2.x release
DefaultContentHandler = ligolw.LIGOLWContentHandler


def ligolw_add(xmldoc, urls, non_lsc_tables_ok = False, verbose = False, **kwargs):
	"""
	An implementation of the LIGO LW add algorithm.  urls is a list of
	URLs (or filenames) to load, xmldoc is the XML document tree to
	which they should be added.  If non_lsc_tables_ok is False (the
	default) then the code will refuse to process documents found to
	contain tables not recognized by the name-->class mapping in
	ligolw.Table.TableByName.  If verbose is True then helpful messages
	are printed to stderr.  All remaining keyword arguments are passed
	to ligo.lw.utils.load_url().
	"""
	# Input
	for n, url in enumerate(urls, 1):
		if verbose:
			sys.stderr.write("%d/%d:" % (n, len(urls)))
		ligolw_utils.load_url(url, xmldoc = xmldoc, verbose = verbose, **kwargs)

	# ID reassignment
	if not non_lsc_tables_ok and lsctables.HasNonLSCTables(xmldoc):
		raise ValueError("non-LSC tables found.  Use --non-lsc-tables-ok to force")
	reassign_ids(xmldoc, verbose = verbose)

	# Document merge
	if verbose:
		sys.stderr.write("merging elements ...\n")
	merge_ligolws(xmldoc)
	merge_compatible_tables(xmldoc)

	return xmldoc
