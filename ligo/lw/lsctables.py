# Copyright (C) 2006--2017  Kipp Cannon
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
LSC Table definitions.

See the LDAS CVS repository at
http://www.ldas-sw.ligo.caltech.edu/cgi-bin/cvsweb.cgi/ldas/dbms/db2/sql
for more information.


Customization
-------------

In some cases, applications will need to define sub-classes of the table
and row classes found here or will need to define their own custom tables
altogether.  Once the custom classes are defined, the following steps are
required to incorporate them into this module's document handling
machinery.

Firstly, if a new Table class is defined, the TableByName mapping defined
in this module should be updated.  The TableByName mapping is used to map
table names to corresponding Python classes.  This mapping is used when
parsing XML documents, when extracting the contents of SQL databases and
any other place the conversion from a name to a class definition is
required.  Once the mapping is updated, XML documents containing Table
elements whose names match the custom definition will be converted to
instances of that class (Tables whose names are not recognized are loaded
as instances of the generic ligo.lw.Table class).

Example:

>>> class MyCustomTable(table.Table):
...	tableName = "custom"
...
>>> TableByName[MyCustomTable.tableName] = MyCustomTable

The row type to be used with a table is selected using the .RowType
attribute of the corresponding Table class.  When parsing an XML document
the text is converted into row objects, each of which is created by calling
the .RowType attribute with no arguments.

Example:

>>> class MyCustomTableRow(table.Table.RowType):
...	pass
...
>>> MyCustomTable.RowType = MyCustomTableRow
"""


import itertools
import math
import numpy
import warnings
from xml import sax


from glue import offsetvector
from glue import segments
import lal
from lal import LIGOTimeGPS
from . import __author__, __date__, __version__
from . import ligolw
from . import table
from . import types as ligolwtypes
from . import ilwd


#
# =============================================================================
#
#                            Convenience Functions
#
# =============================================================================
#


def New(cls, columns = None, **kwargs):
	"""
	Construct a pre-defined LSC table.  The optional columns argument
	is a sequence of the names of the columns the table is to be
	constructed with.  If columns = None, then the table is constructed
	with all valid columns (use columns = [] to create a table with no
	columns).

	Example:

	>>> import sys
	>>> tbl = New(ProcessTable, [u"process_id", u"start_time", u"end_time", u"comment"])
	>>> tbl.write(sys.stdout)	# doctest: +NORMALIZE_WHITESPACE
	<Table Name="process:table">
		<Column Type="int_8s" Name="process_id"/>
		<Column Type="int_4s" Name="start_time"/>
		<Column Type="int_4s" Name="end_time"/>
		<Column Type="lstring" Name="comment"/>
		<Stream Delimiter="," Type="Local" Name="process:table">
		</Stream>
	</Table>
	"""
	new = cls(sax.xmlreader.AttributesImpl({u"Name": cls.TableName.enc(cls.tableName)}), **kwargs)
	for name in columns if columns is not None else sorted(new.validcolumns):
		new.appendColumn(name)
	new._end_of_columns()
	new.appendChild(table.TableStream(sax.xmlreader.AttributesImpl({u"Name": new.getAttribute(u"Name"), u"Delimiter": table.TableStream.Delimiter.default, u"Type": table.TableStream.Type.default})))
	return new


def HasNonLSCTables(elem):
	"""
	Return True if the document tree below elem contains non-LSC
	tables, otherwise return False.
	"""
	return any(t.Name not in TableByName for t in elem.getElementsByTagName(ligolw.Table.tagName))


class instrumentsproperty(object):
	def __init__(self, name):
		self.name = name

	@staticmethod
	def get(ifos):
		"""
		Parse the values stored in the "ifos" and "instruments"
		columns found in many tables.  This function is mostly for
		internal use by the .instruments properties of the
		corresponding row classes.  The mapping from input to
		output is as follows (rules are applied in order):

		input is None --> output is None

		input contains "," --> output is set of strings split on
		"," with leading and trailing whitespace stripped from each
		piece and empty strings removed from the set

		input contains "+" --> output is set of strings split on
		"+" with leading and trailing whitespace stripped from each
		piece and empty strings removed from the set

		else, after stripping input of leading and trailing
		whitespace,

		input has an even length greater than two --> output is set
		of two-character pieces

		input is a non-empty string --> output is a set containing
		input as single value

		else output is an empty set.

		NOTE:  the complexity of this algorithm is a consequence of
		there being several conventions in use for encoding a set
		of instruments into one of these columns;  it has been
		proposed that L.L.W.  documents standardize on the
		comma-delimited variant of the encodings recognized by this
		function, and for this reason the inverse function,
		instrumentsproperty.set(), implements that encoding only.

		NOTE:  to force a string containing an even number of
		characters to be interpreted as a single instrument name
		and not to be be split into two-character pieces, add a ","
		character to the end to force the comma-delimited decoding
		to be used.  instrumentsproperty.set() does this for you.

		Example:

		>>> print(instrumentsproperty.get(None))
		None
		>>> instrumentsproperty.get(u"")
		set([])
		>>> instrumentsproperty.get(u"  ,  ,,")
		set([])
		>>> instrumentsproperty.get(u"H1")
		set([u'H1'])
		>>> instrumentsproperty.get(u"SWIFT")
		set([u'SWIFT'])
		>>> instrumentsproperty.get(u"H1L1")
		set([u'H1', u'L1'])
		>>> instrumentsproperty.get(u"H1L1,")
		set([u'H1L1'])
		>>> instrumentsproperty.get(u"H1,L1")
		set([u'H1', u'L1'])
		>>> instrumentsproperty.get(u"H1+L1")
		set([u'H1', u'L1'])
		"""
		if ifos is None:
			return None
		if u"," in ifos:
			result = set(ifo.strip() for ifo in ifos.split(u","))
			result.discard(u"")
			return result
		if u"+" in ifos:
			result = set(ifo.strip() for ifo in ifos.split(u"+"))
			result.discard(u"")
			return result
		ifos = ifos.strip()
		if len(ifos) > 2 and not len(ifos) % 2:
			# if ifos is a string with an even number of
			# characters greater than two, split it into
			# two-character pieces.  FIXME:  remove this when
			# the inspiral codes don't write ifos strings like
			# this anymore
			return set(ifos[n:n+2] for n in range(0, len(ifos), 2))
		if ifos:
			return set([ifos])
		return set()

	@staticmethod
	def set(instruments):
		"""
		Convert an iterable of instrument names into a value
		suitable for storage in the "ifos" column found in many
		tables.  This function is mostly for internal use by the
		.instruments properties of the corresponding row classes.
		The input can be None or an iterable of zero or more
		instrument names, none of which may be zero-length, consist
		exclusively of spaces, or contain "," or "+" characters.
		The output is a single string containing the unique
		instrument names concatenated using "," as a delimiter.
		instruments will only be iterated over once and so can be a
		generator expression.  Whitespace is allowed in instrument
		names but might not be preserved.  Repeated names will not
		be preserved.

		NOTE:  in the special case that there is 1 instrument name
		in the iterable and it has an even number of characters > 2
		in it, the output will have a "," appended in order to
		force instrumentsproperty.get() to parse the string back
		into a single instrument name.  This is a special case
		included temporarily to disambiguate the encoding until all
		codes have been ported to the comma-delimited encoding.
		This behaviour will be discontinued at that time.  DO NOT
		WRITE CODE THAT RELIES ON THIS!  You have been warned.

		Example:

		>>> print(instrumentsproperty.set(None))
		None
		>>> instrumentsproperty.set(())
		u''
		>>> instrumentsproperty.set((u"H1",))
		u'H1'
		>>> instrumentsproperty.set((u"H1",u"H1",u"H1"))
		u'H1'
		>>> instrumentsproperty.set((u"H1",u"L1"))
		u'H1,L1'
		>>> instrumentsproperty.set((u"SWIFT",))
		u'SWIFT'
		>>> instrumentsproperty.set((u"H1L1",))
		u'H1L1,'
		"""
		if instruments is None:
			return None
		_instruments = sorted(set(instrument.strip() for instrument in instruments))
		# safety check:  refuse to accept blank names, or names
		# with commas or pluses in them as they cannot survive the
		# encode/decode process
		if not all(_instruments) or any(u"," in instrument or u"+" in instrument for instrument in _instruments):
			raise ValueError(instruments)
		if len(_instruments) == 1 and len(_instruments[0]) > 2 and not len(_instruments[0]) % 2:
			# special case disambiguation.  FIXME:  remove when
			# everything uses the comma-delimited encoding
			return u"%s," % _instruments[0]
		return u",".join(_instruments)

	def __get__(self, obj, type = None):
		return self.get(getattr(obj, self.name))

	def __set__(self, obj, instruments):
		setattr(obj, self.name, self.set(instruments))


class gpsproperty(object):
	"""
	Descriptor used internally to implement LIGOTimeGPS-valued
	properties.
	"""
	def __init__(self, s_name, ns_name):
		self.s_name = s_name
		self.ns_name = ns_name

	posinf = 0x7FFFFFFF, 0xFFFFFFFF
	neginf = 0xFFFFFFFF, 0xFFFFFFFF

	def __get__(self, obj, type = None):
		s = getattr(obj, self.s_name)
		ns = getattr(obj, self.ns_name)
		if s is None and ns is None:
			return None
		if (s, ns) == self.posinf:
			return segments.PosInfinity
		if (s, ns) == self.neginf:
			return segments.NegInfinity
		return LIGOTimeGPS(s, ns)

	def __set__(self, obj, gps):
		if gps is None:
			s = ns = None
		elif isinstance(gps, segments.infinity) or math.isinf(gps):
			if gps > 0:
				s, ns = self.posinf
			elif gps < 0:
				s, ns = self.neginf
			else:
				raise ValueError(gps)
		else:
			try:
				s = gps.gpsSeconds
				ns = gps.gpsNanoSeconds
			except AttributeError:
				# try converting and going again
				return self.__set__(obj, LIGOTimeGPS(gps))
			if abs(ns) > 999999999:
				raise ValueError("denormalized LIGOTimeGPS not allowed")
		setattr(obj, self.s_name, s)
		setattr(obj, self.ns_name, ns)


class gpsproperty_with_gmst(gpsproperty):
	def __init__(self, s_name, ns_name, gmst_name):
		super(gpsproperty_with_gmst, self).__init__(s_name, ns_name)
		self.gmst_name = gmst_name

	def __set__(self, obj, gps):
		super(gpsproperty_with_gmst, self).__set__(obj, gps)
		if gps is None:
			setattr(obj, self.gmst_name, None)
		else:
			# re-retrieve the value in case it required type
			# conversion
			gps = self.__get__(obj)
			setattr(obj, self.gmst_name, lal.GreenwichMeanSiderealTime(gps))


class segmentproperty(object):
	"""
	Descriptor used internally to expose pairs of GPS-valued properties
	as segment-valued properties.
	"""
	def __init__(self, start_name, stop_name):
		self.start = start_name
		self.stop = stop_name

	def __get__(self, obj, type = None):
		start = getattr(obj, self.start)
		stop = getattr(obj, self.stop)
		if start is None and stop is None:
			return None
		return segments.segment(start, stop)

	def __set__(self, obj, seg):
		if seg is None:
			start = stop = None
		else:
			start, stop = seg
		setattr(obj, self.start, start)
		setattr(obj, self.stop, stop)


#
# =============================================================================
#
#                                process:table
#
# =============================================================================
#


ProcessID = table.next_id.type(u"process_id")


class ProcessTable(table.Table):
	tableName = "process"
	validcolumns = {
		"program": "lstring",
		"version": "lstring",
		"cvs_repository": "lstring",
		"cvs_entry_time": "int_4s",
		"comment": "lstring",
		"is_online": "int_4s",
		"node": "lstring",
		"username": "lstring",
		"unix_procid": "int_4s",
		"start_time": "int_4s",
		"end_time": "int_4s",
		"jobid": "int_4s",
		"domain": "lstring",
		"ifos": "lstring",
		"process_id": "int_8s"
	}
	constraints = "PRIMARY KEY (process_id)"
	next_id = ProcessID(0)

	def get_ids_by_program(self, program):
		"""
		Return a set containing the process IDs from rows whose
		program string equals the given program.
		"""
		return set(row.process_id for row in self if row.program == program)


class Process(table.Table.RowType):
	"""
	Example:

	>>> x = Process()
	>>> x.instruments = (u"H1", u"L1")
	>>> x.ifos
	u'H1,L1'
	>>> x.instruments
	set([u'H1', u'L1'])
	"""
	__slots__ = tuple(map(table.Column.ColumnName, ProcessTable.validcolumns))

	instruments = instrumentsproperty("ifos")


ProcessTable.RowType = Process


#
# =============================================================================
#
#                             process_params:table
#
# =============================================================================
#


class ProcessParamsTable(table.Table):
	tableName = "process_params"
	validcolumns = {
		"program": "lstring",
		"process:process_id": "int_8s",
		"param": "lstring",
		"type": "lstring",
		"value": "lstring"
	}
	# FIXME: these constraints break ID remapping in the DB backend.
	# an index is used instead.  switch back to the constraints when I
	# can figure out how not to break remapping.
	#constraints = "PRIMARY KEY (process_id, param)"
	how_to_index = {
		"pp_pip_index": ("process_id", "param"),
	}

	def append(self, row):
		if row.type is not None and row.type not in ligolwtypes.Types:
			raise ligolw.ElementError("unrecognized type '%s'" % row.type)
		super(ProcessParamsTable, self).append(row)


class ProcessParams(table.Table.RowType):
	"""
	Example:

	>>> x = ProcessParams()
	>>> x.pyvalue = u"test"
	>>> x.type
	u'lstring'
	>>> x.value
	u'test'
	>>> x.pyvalue
	u'test'
	>>> x.pyvalue = 6.
	>>> x.type
	u'real_8'
	>>> x.value
	u'6'
	>>> x.pyvalue
	6.0
	>>> x.pyvalue = None
	>>> print(x.type)
	None
	>>> print(x.value)
	None
	>>> print(x.pyvalue)
	None
	>>> x.pyvalue = True
	>>> x.type
	u'int_4s'
	>>> x.value
	u'1'
	>>> x.pyvalue
	1
	"""
	__slots__ = tuple(map(table.Column.ColumnName, ProcessParamsTable.validcolumns))

	@property
	def pyvalue(self):
		if self.value is None:
			return None
		try:
			parsefunc = ligolwtypes.ToPyType[self.type]
		except KeyError:
			raise ValueError("invalid type '%s'" % self.type)
		return parsefunc(self.value)

	@pyvalue.setter
	def pyvalue(self, value):
		if value is None:
			self.type = self.value = None
		else:
			try:
				self.type = ligolwtypes.FromPyType[type(value)]
			except KeyError:
				raise ValueError("type not supported: %s" % repr(type(value)))
			self.value = value if self.type in ligolwtypes.StringTypes else ligolwtypes.FormatFunc[self.type](value)


ProcessParamsTable.RowType = ProcessParams


#
# =============================================================================
#
#                             search_summary:table
#
# =============================================================================
#


class SearchSummaryTable(table.Table):
	tableName = "search_summary"
	validcolumns = {
		"process:process_id": "int_8s",
		"shared_object": "lstring",
		"lalwrapper_cvs_tag": "lstring",
		"lal_cvs_tag": "lstring",
		"comment": "lstring",
		"ifos": "lstring",
		"in_start_time": "int_4s",
		"in_start_time_ns": "int_4s",
		"in_end_time": "int_4s",
		"in_end_time_ns": "int_4s",
		"out_start_time": "int_4s",
		"out_start_time_ns": "int_4s",
		"out_end_time": "int_4s",
		"out_end_time_ns": "int_4s",
		"nevents": "int_4s",
		"nnodes": "int_4s"
	}
	how_to_index = {
		"ss_pi_index": ("process_id",),
	}

	def get_in_segmentlistdict(self, process_ids = None):
		"""
		Return a segmentlistdict mapping instrument to in segment
		list.  If process_ids is a sequence of process IDs, then
		only rows with matching IDs are included otherwise all rows
		are included.

		Note:  the result is not coalesced, each segmentlist
		contains the segments listed for that instrument as they
		appeared in the table.
		"""
		seglists = segments.segmentlistdict()
		for row in self:
			ifos = row.instruments or (None,)
			if process_ids is None or row.process_id in process_ids:
				seglists.extend(dict((ifo, segments.segmentlist([row.in_segment])) for ifo in ifos))
		return seglists

	def get_out_segmentlistdict(self, process_ids = None):
		"""
		Return a segmentlistdict mapping instrument to out segment
		list.  If process_ids is a sequence of process IDs, then
		only rows with matching IDs are included otherwise all rows
		are included.

		Note:  the result is not coalesced, each segmentlist
		contains the segments listed for that instrument as they
		appeared in the table.
		"""
		seglists = segments.segmentlistdict()
		for row in self:
			ifos = row.instruments or (None,)
			if process_ids is None or row.process_id in process_ids:
				seglists.extend(dict((ifo, segments.segmentlist([row.out_segment])) for ifo in ifos))
		return seglists


class SearchSummary(table.Table.RowType):
	"""
	Example:

	>>> x = SearchSummary()
	>>> x.instruments = (u"H1", u"L1")
	>>> x.ifos
	u'H1,L1'
	>>> x.instruments
	set([u'H1', u'L1'])
	>>> x.in_start = x.out_start = LIGOTimeGPS(0)
	>>> x.in_end = x.out_end = LIGOTimeGPS(10)
	>>> x.in_segment
	segment(LIGOTimeGPS(0, 0), LIGOTimeGPS(10, 0))
	>>> x.out_segment
	segment(LIGOTimeGPS(0, 0), LIGOTimeGPS(10, 0))
	>>> x.in_segment = x.out_segment = None
	>>> print(x.in_segment)
	None
	>>> print(x.out_segment)
	None
	"""
	__slots__ = tuple(map(table.Column.ColumnName, SearchSummaryTable.validcolumns))

	instruments = instrumentsproperty("ifos")

	in_start = gpsproperty("in_start_time", "in_start_time_ns")
	in_end = gpsproperty("in_end_time", "in_end_time_ns")
	out_start = gpsproperty("out_start_time", "out_start_time_ns")
	out_end = gpsproperty("out_end_time", "out_end_time_ns")

	in_segment = segmentproperty("in_start", "in_end")
	out_segment = segmentproperty("out_start", "out_end")


SearchSummaryTable.RowType = SearchSummary


#
# =============================================================================
#
#                            search_summvars:table
#
# =============================================================================
#


SearchSummVarsID = table.next_id.type(u"search_summvar_id")


class SearchSummVarsTable(table.Table):
	tableName = "search_summvars"
	validcolumns = {
		"process:process_id": "int_8s",
		"search_summvar_id": "int_8s",
		"name": "lstring",
		"string": "lstring",
		"value": "real_8"
	}
	constraints = "PRIMARY KEY (search_summvar_id)"
	next_id = SearchSummVarsID(0)


class SearchSummVars(table.Table.RowType):
	__slots__ = tuple(map(table.Column.ColumnName, SearchSummVarsTable.validcolumns))


SearchSummVarsTable.RowType = SearchSummVars


#
# =============================================================================
#
#                            experiment:table
#
# =============================================================================
#


ExpDefID = table.next_id.type(u"experiment_id")


class ExperimentTable(table.Table):
	tableName = "experiment"
	validcolumns = {
		"experiment_id": "int_8s",
		"search_group": "lstring",
		"search": "lstring",
		"lars_id": "lstring",
		"instruments": "lstring",
		"gps_start_time": "int_4s",
		"gps_end_time": "int_4s",
		"comments": "lstring"
	}
	constraints = "PRIMARY KEY (experiment_id)"
	next_id = ExpDefID(0)

	def get_expr_id(self, search_group, search, lars_id, instruments, gps_start_time, gps_end_time, comments = None):
		"""
		Return the expr_def_id for the row in the table whose
		values match the givens.
		If a matching row is not found, returns None.

		@search_group: string representing the search group (e.g., cbc)
		@serach: string representing search (e.g., inspiral)
		@lars_id: string representing lars_id
		@instruments: the instruments; must be a python set
		@gps_start_time: string or int representing the gps_start_time of the experiment
		@gps_end_time: string or int representing the gps_end_time of the experiment
		"""
		# create string from instrument set
		instruments = ifos_from_instrument_set(instruments)

		# look for the ID
		for row in self:
			if (row.search_group, row.search, row.lars_id, row.instruments, row.gps_start_time, row.gps_end_time, row.comments) == (search_group, search, lars_id, instruments, gps_start_time, gps_end_time, comments):
				# found it
				return row.experiment_id

		# experiment not found in table
		return None

	def write_new_expr_id(self, search_group, search, lars_id, instruments, gps_start_time, gps_end_time, comments = None):
		"""
		Creates a new def_id for the given arguments and returns it. 
		If an entry already exists with these, will just return that id.

		@search_group: string representing the search group (e.g., cbc)
		@serach: string representing search (e.g., inspiral)
		@lars_id: string representing lars_id
		@instruments: the instruments; must be a python set
		@gps_start_time: string or int representing the gps_start_time of the experiment
		@gps_end_time: string or int representing the gps_end_time of the experiment
		"""
		
		# check if id already exists
		check_id = self.get_expr_id( search_group, search, lars_id, instruments, gps_start_time, gps_end_time, comments = comments )
		if check_id:
			return check_id

		# experiment not found in table
		row = self.RowType()
		row.experiment_id = self.get_next_id()
		row.search_group = search_group
		row.search = search
		row.lars_id = lars_id
		row.instruments = ifos_from_instrument_set(instruments)
		row.gps_start_time = gps_start_time
		row.gps_end_time = gps_end_time
		row.comments = comments
		self.append(row)

		# return new ID
		return row.experiment_id

	def get_row_from_id(self, experiment_id):
		"""
		Returns row in matching the given experiment_id.
		"""
		row = [row for row in self if row.experiment_id == experiment_id]
		if len(row) > 1:
			raise ValueError("duplicate ids in experiment table")
		if len(row) == 0:
			raise ValueError("id '%s' not found in table" % experiment_id)

		return row[0]


class Experiment(table.Table.RowType):
	__slots__ = tuple(map(table.Column.ColumnName, ExperimentTable.validcolumns))

	insts = instrumentsproperty("instruments")


ExperimentTable.RowType = Experiment


#
# =============================================================================
#
#                            experiment_summary:table
#
# =============================================================================
#


ExpSummID = table.next_id.type(u"experiment_summ_id")


class ExperimentSummaryTable(table.Table):
	tableName = "experiment_summary"
	validcolumns = {
		"experiment_summ_id": "int_8s",
		"experiment:experiment_id": "int_8s",
		"time_slide:time_slide_id": "int_8s",
		"veto_def_name": "lstring",
		"datatype": "lstring",
		"sim_proc_id": "ilwd:char",
		"duration": "int_4s",
		"nevents": "int_4u"
	}
	constraints = "PRIMARY KEY (experiment_summ_id)"
	how_to_index = {
		"es_ei_index": ("experiment_id",),
		"es_dt_index": ("datatype",)
	}
	next_id = ExpSummID(0)

	datatypes = ['slide', 'all_data', 'playground', 'exclude_play', 'simulation']
		

	def as_id_dict(self):
		"""
		Return table as a dictionary mapping experiment_id, time_slide_id,
		veto_def_name, and sim_proc_id (if it exists) to the expr_summ_id.
		"""
		d = {}
		for row in self:
			if row.experiment_id not in d:
				d[row.experiment_id] = {}
			if (row.time_slide_id, row.veto_def_name, row.datatype, row.sim_proc_id) in d[row.experiment_id]:
				# entry already exists, raise error
				raise KeyError("duplicate entries in experiment_summary table")
			d[row.experiment_id][(row.time_slide_id, row.veto_def_name, row.datatype, row.sim_proc_id)] = row.experiment_summ_id

		return d

	def get_expr_summ_id(self, experiment_id, time_slide_id, veto_def_name, datatype, sim_proc_id = None):
		"""
		Return the expr_summ_id for the row in the table whose experiment_id, 
		time_slide_id, veto_def_name, and datatype match the given. If sim_proc_id,
		will retrieve the injection run matching that sim_proc_id.
		If a matching row is not found, returns None.
		"""

		# look for the ID
		for row in self:
			if (row.experiment_id, row.time_slide_id, row.veto_def_name, row.datatype, row.sim_proc_id) == (experiment_id, time_slide_id, veto_def_name, datatype, sim_proc_id):
				# found it
				return row.experiment_summ_id

		# if get to here, experiment not found in table
		return None

	def write_experiment_summ(self, experiment_id, time_slide_id, veto_def_name, datatype, sim_proc_id = None ):
		"""
		Writes a single entry to the experiment_summ table. This can be used
		for either injections or non-injection experiments. However, it is
		recommended that this only be used for injection experiments; for
		non-injection experiments write_experiment_summ_set should be used to
		ensure that an entry gets written for every time-slide performed.
		"""
		# check if entry alredy exists; if so, return value
		check_id = self.get_expr_summ_id(experiment_id, time_slide_id, veto_def_name, datatype, sim_proc_id = sim_proc_id)
		if check_id:
			return check_id

		row = self.RowType()
		row.experiment_summ_id = self.get_next_id()
		row.experiment_id = experiment_id
		row.time_slide_id = time_slide_id
		row.veto_def_name = veto_def_name
		row.datatype = datatype
		row.sim_proc_id = sim_proc_id
		row.nevents = None
		row.duration = None
		self.append(row)
		
		return row.experiment_summ_id

	def write_non_injection_summary(self, experiment_id, time_slide_dict, veto_def_name, write_all_data = True, write_playground = True, write_exclude_play = True, return_dict = False):
		"""
		Method for writing a new set of non-injection experiments to the experiment
		summary table. This ensures that for every entry in the 
		experiment table, an entry for every slide is added to
		the experiment_summ table, rather than just an entry for slides that
		have events in them. Default is to write a 3 rows for zero-lag: one for
		all_data, playground, and exclude_play. (If all of these are set to false,
		will only slide rows.)
		
		Note: sim_proc_id is hard-coded to None because time-slides
		are not performed with injections.

		@experiment_id: the experiment_id for this experiment_summary set
		@time_slide_dict: the time_slide table as a dictionary; used to figure out
			what is zero-lag and what is slide
		@veto_def_name: the name of the vetoes applied
		@write_all_data: if set to True, writes a zero-lag row who's datatype column
			is set to 'all_data'
		@write_playground: same, but datatype is 'playground'
		@write_exclude_play: same, but datatype is 'exclude_play'
		@return_dict: if set to true, returns an id_dict of the table
		"""
		for slide_id in time_slide_dict:
			# check if it's zero_lag or not
			if not any( time_slide_dict[slide_id].values() ):
				if write_all_data:
					self.write_experiment_summ( experiment_id, slide_id, veto_def_name, 'all_data', sim_proc_id = None )
				if write_playground:
					self.write_experiment_summ( experiment_id, slide_id, veto_def_name, 'playground', sim_proc_id = None )
				if write_exclude_play:
					self.write_experiment_summ( experiment_id, slide_id, veto_def_name, 'exclude_play', sim_proc_id = None )
			else:
				self.write_experiment_summ( experiment_id, slide_id, veto_def_name, 'slide', sim_proc_id = None )

		if return_dict:
			return self.as_id_dict()


	def add_nevents(self, experiment_summ_id, num_events, add_to_current = True):
		"""
		Add num_events to the nevents column in a specific entry in the table. If
		add_to_current is set to False, will overwrite the current nevents entry in
		the row with num_events. Otherwise, default is to add num_events to
		the current value.

		Note: Can subtract events by passing a negative number to num_events.
		"""
		for row in self:
			if row.experiment_summ_id != experiment_summ_id:
				continue
			if row.nevents is None:
				row.nevents = 0
			if add_to_current:
				row.nevents += num_events
				return row.nevents
			else:
				row.nevents = num_events
				return row.nevents
				
		# if get to here, couldn't find experiment_summ_id in the table
		raise ValueError("'%s' could not be found in the table" % (str(experiment_summ_id)))


class ExperimentSummary(table.Table.RowType):
	__slots__ = tuple(map(table.Column.ColumnName, ExperimentSummaryTable.validcolumns))


ExperimentSummaryTable.RowType = ExperimentSummary


#
# =============================================================================
#
#                            experiment_map:table
#
# =============================================================================
#


class ExperimentMapTable(table.Table):
	tableName = "experiment_map"
	validcolumns = {
		"experiment_summary:experiment_summ_id": "int_8s",
		"coinc_event:coinc_event_id": "int_8s",
	}
	how_to_index = {
		"em_esi_index": ("experiment_summ_id",),
		"em_cei_index": ("coinc_event_id",)
	}

	def get_experiment_summ_ids( self, coinc_event_id ):
		"""
		Gets all the experiment_summ_ids that map to a given coinc_event_id.
		"""
		experiment_summ_ids = []
		for row in self:
			if row.coinc_event_id == coinc_event_id:
				experiment_summ_ids.append(row.experiment_summ_id)
		if len(experiment_summ_ids) == 0:
			raise ValueError("'%s' could not be found in the experiment_map table" % coinc_event_id)
		return experiment_summ_ids


class ExperimentMap(table.Table.RowType):
	__slots__ = tuple(map(table.Column.ColumnName, ExperimentMapTable.validcolumns))


ExperimentMapTable.RowType = ExperimentMap


#
# =============================================================================
#
#                               sngl_burst:table
#
# =============================================================================
#


SnglBurstID = table.next_id.type(u"event_id")


class SnglBurstTable(table.Table):
	tableName = "sngl_burst"
	validcolumns = {
		"creator_db": "int_4s",
		"process:process_id": "int_8s",
		"filter:filter_id": "int_8s",
		"ifo": "lstring",
		"search": "lstring",
		"channel": "lstring",
		"start_time": "int_4s",
		"start_time_ns": "int_4s",
		"stop_time": "int_4s",
		"stop_time_ns": "int_4s",
		"duration": "real_4",
		"flow": "real_4",
		"fhigh": "real_4",
		"central_freq": "real_4",
		"bandwidth": "real_4",
		"amplitude": "real_4",
		"snr": "real_4",
		"confidence": "real_4",
		"chisq": "real_8",
		"chisq_dof": "real_8",
		"tfvolume": "real_4",
		"hrss": "real_4",
		"time_lag": "real_4",
		"peak_time": "int_4s",
		"peak_time_ns": "int_4s",
		"peak_frequency": "real_4",
		"peak_strain": "real_4",
		"peak_time_error": "real_4",
		"peak_frequency_error": "real_4",
		"peak_strain_error": "real_4",
		"ms_start_time": "int_4s",
		"ms_start_time_ns": "int_4s",
		"ms_stop_time": "int_4s",
		"ms_stop_time_ns": "int_4s",
		"ms_duration": "real_4",
		"ms_flow": "real_4",
		"ms_fhigh": "real_4",
		"ms_bandwidth": "real_4",
		"ms_hrss": "real_4",
		"ms_snr": "real_4",
		"ms_confidence": "real_4",
		"param_one_name": "lstring",
		"param_one_value": "real_8",
		"param_two_name": "lstring",
		"param_two_value": "real_8",
		"param_three_name": "lstring",
		"param_three_value": "real_8",
		"event_id": "int_8s"
	}
	constraints = "PRIMARY KEY (event_id)"
	next_id = SnglBurstID(0)
	interncolumns = ("ifo", "search", "channel")


class SnglBurst(table.Table.RowType):
	__slots__ = tuple(map(table.Column.ColumnName, SnglBurstTable.validcolumns))

	#
	# Tile properties
	#

	start = gpsproperty("start_time", "start_time_ns")
	stop = gpsproperty("stop_time", "stop_time_ns")
	peak = gpsproperty("peak_time", "peak_time_ns")

	@property
	def period(self):
		start = self.start
		try:
			stop = self.stop
		except AttributeError:
			stop = None
		# special case:  use duration if stop is not recorded
		if start is not None and stop is None and self.duration is not None:
			stop = start + self.duration
		if start is None and stop is None:
			return None
		return segments.segment(start, stop)

	@period.setter
	def period(self, seg):
		if seg is None:
			self.start = self.stop = self.duration = None
		else:
			self.start, self.stop = seg
			self.duration = float(abs(seg))

	@property
	def band(self):
		if self.central_freq is None and self.bandwidth is None:
			return None
		return segments.segment(self.central_freq - self.bandwidth / 2., self.central_freq + self.bandwidth / 2.)

	@band.setter
	def band(self, seg):
		if seg is None:
			try:
				self.flow = self.fhigh = None
			except AttributeError:
				# not in LAL C version
				pass
			self.central_freq = self.bandwidth = None
		else:
			try:
				self.flow, self.fhigh = seg
			except AttributeError:
				# not in LAL C version
				pass
			self.central_freq = sum(seg) / 2.
			self.bandwidth = abs(seg)

	#
	# "Most significant pixel" properties
	#

	ms_start = gpsproperty("ms_start_time", "ms_start_time_ns")
	ms_stop = gpsproperty("ms_stop_time", "ms_stop_time_ns")
	ms_peak = gpsproperty("ms_peak_time", "ms_peak_time_ns")

	@property
	def ms_period(self):
		start = self.ms_start
		stop = self.ms_stop
		# special case:  use duration if stop is not recorded
		if start is not None and stop is None and self.ms-duration is not None:
			stop = start + self.ms_duration
		if start is None and stop is None:
			return None
		return segments.segment(start, stop)

	@ms_period.setter
	def ms_period(self, seg):
		if seg is None:
			self.ms_start = self.ms_stop = self.ms_duration = None
		else:
			self.ms_start, self.ms_stop = seg
			self.ms_duration = float(abs(seg))

	@property
	def ms_band(self):
		if self.ms_flow is None and self.ms_bandwidth is None:
			return None
		return segments.segment(self.ms_flow, self.ms_flow + self.ms_bandwidth)

	@ms_band.setter
	def ms_band(self, seg):
		if seg is None:
			self.ms_bandwidth = self.ms_flow = self.ms_fhigh = None
		else:
			self.ms_flow, self.ms_fhigh = seg
			self.ms_bandwidth = abs(seg)


SnglBurstTable.RowType = SnglBurst


#
# =============================================================================
#
#                             sngl_inspiral:table
#
# =============================================================================
#


SnglInspiralID = table.next_id.type(u"event_id")


class SnglInspiralTable(table.Table):
	tableName = "sngl_inspiral"
	validcolumns = {
		"process:process_id": "int_8s",
		"ifo": "lstring",
		"search": "lstring",
		"channel": "lstring",
		"end_time": "int_4s",
		"end_time_ns": "int_4s",
		"end_time_gmst": "real_8",
		"impulse_time": "int_4s",
		"impulse_time_ns": "int_4s",
		"template_duration": "real_8",
		"event_duration": "real_8",
		"amplitude": "real_4",
		"eff_distance": "real_4",
		"coa_phase": "real_4",
		"mass1": "real_4",
		"mass2": "real_4",
		"mchirp": "real_4",
		"mtotal": "real_4",
		"eta": "real_4",
		"kappa": "real_4",
		"chi": "real_4",
		"tau0": "real_4",
		"tau2": "real_4",
		"tau3": "real_4",
		"tau4": "real_4",
		"tau5": "real_4",
		"ttotal": "real_4",
		"psi0": "real_4",
		"psi3": "real_4",
		"alpha": "real_4",
		"alpha1": "real_4",
		"alpha2": "real_4",
		"alpha3": "real_4",
		"alpha4": "real_4",
		"alpha5": "real_4",
		"alpha6": "real_4",
		"beta": "real_4",
		"f_final": "real_4",
		"snr": "real_4",
		"chisq": "real_4",
		"chisq_dof": "int_4s",
		"bank_chisq": "real_4",
		"bank_chisq_dof": "int_4s",
		"cont_chisq": "real_4",
		"cont_chisq_dof": "int_4s",
		"sigmasq": "real_8",
		"rsqveto_duration": "real_4",
		"Gamma0": "real_4",
		"Gamma1": "real_4",
		"Gamma2": "real_4",
		"Gamma3": "real_4",
		"Gamma4": "real_4",
		"Gamma5": "real_4",
		"Gamma6": "real_4",
		"Gamma7": "real_4",
		"Gamma8": "real_4",
		"Gamma9": "real_4",
		"spin1x": "real_4",
		"spin1y": "real_4",
		"spin1z": "real_4",
		"spin2x": "real_4",
		"spin2y": "real_4",
		"spin2z": "real_4",
		"event_id": "int_8s"
	}
	constraints = "PRIMARY KEY (event_id)"
	next_id = SnglInspiralID(0)
	interncolumns = ("ifo", "search", "channel")


class SnglInspiral(table.Table.RowType):
	__slots__ = tuple(map(table.Column.ColumnName, SnglInspiralTable.validcolumns))

	@staticmethod
	def chirp_distance(dist, mchirp, ref_mass=1.4):
		return dist * (2.**(-1./5) * ref_mass / mchirp)**(5./6)

	#
	# Properties
	#

	end = gpsproperty("end_time", "end_time_ns")

	@property
	def spin1(self):
		if self.spin1x is None and self.spin1y is None and self.spin1z is None:
			return None
		return numpy.array((self.spin1x, self.spin1y, self.spin1z), dtype = "double")

	@spin1.setter
	def spin1(self, spin):
		if spin is None:
			self.spin1x = self.spin1y = self.spin1z = None
		else:
			self.spin1x, self.spin1y, self.spin1z = spin

	@property
	def spin2(self):
		if self.spin2x is None and self.spin2y is None and self.spin2z is None:
			return None
		return numpy.array((self.spin2x, self.spin2y, self.spin2z), dtype = "double")

	@spin2.setter
	def spin2(self, spin):
		if spin is None:
			self.spin2x = self.spin2y = self.spin2z = None
		else:
			self.spin2x, self.spin2y, self.spin2z = spin

	#
	# Methods
	#

	# FIXME: how are two inspiral events defined to be the same?
	def __eq__(self, other):
		return not (
			cmp(self.ifo, other.ifo) or
			cmp(self.end, other.end) or
			cmp(self.mass1, other.mass1) or
			cmp(self.mass2, other.mass2) or
			cmp(self.spin1, other.spin1) or
			cmp(self.spin2, other.spin2) or
			cmp(self.search, other.search)
		)


SnglInspiralTable.RowType = SnglInspiral


#
# =============================================================================
#
#                             coinc_inspiral:table
#
# =============================================================================
#


class CoincInspiralTable(table.Table):
	tableName = "coinc_inspiral"
	validcolumns = {
		"coinc_event:coinc_event_id": "int_8s",
		"ifos": "lstring",
		"end_time": "int_4s",
		"end_time_ns": "int_4s",
		"mass": "real_8",
		"mchirp": "real_8",
		"minimum_duration": "real_8",
		"snr": "real_8",
		"false_alarm_rate": "real_8",
		"combined_far": "real_8"
	}
	# FIXME:  like some other tables here, this table should have the
	# constraint that the coinc_event_id column is a primary key.  this
	# breaks ID reassignment in ligolw_sqlite, so until that is fixed
	# the constraint is being replaced with an index.
	#constraints = "PRIMARY KEY (coinc_event_id)"
	how_to_index = {
		"ci_cei_index": ("coinc_event_id",)
	}
	interncolumns = ("ifos",)


class CoincInspiral(table.Table.RowType):
	"""
	Example:

	>>> x = CoincInspiral()
	>>> x.instruments = (u"H1", u"L1")
	>>> x.ifos
	u'H1,L1'
	>>> x.instruments
	set([u'H1', u'L1'])
	>>> x.end = LIGOTimeGPS(10)
	>>> x.end
	LIGOTimeGPS(10, 0)
	>>> x.end = None
	>>> print(x.end)
	None
	"""
	__slots__ = tuple(map(table.Column.ColumnName, CoincInspiralTable.validcolumns))

	instruments = instrumentsproperty("ifos")

	end = gpsproperty("end_time", "end_time_ns")


CoincInspiralTable.RowType = CoincInspiral


#
# =============================================================================
#
#                             sngl_ringdown:table
#
# =============================================================================
#


SnglRingdownID = table.next_id.type(u"event_id")


class SnglRingdownTable(table.Table):
	tableName = "sngl_ringdown"
	validcolumns = {
		"process:process_id": "int_8s",
		"ifo": "lstring",
		"channel": "lstring",
		"start_time": "int_4s",
		"start_time_ns": "int_4s",
		"start_time_gmst": "real_8",
		"frequency": "real_4",
		"quality": "real_4",
		"phase": "real_4",
		"mass": "real_4",
		"spin": "real_4",
		"epsilon": "real_4",
		"num_clust_trigs": "int_4s",
		"ds2_H1H2": "real_4",
		"ds2_H1L1": "real_4",
		"ds2_H1V1": "real_4",
		"ds2_H2L1": "real_4",
		"ds2_H2V1": "real_4",
		"ds2_L1V1": "real_4",
		"amplitude": "real_4",
		"snr": "real_4",
		"eff_dist": "real_4",
		"sigma_sq": "real_8",
		"event_id": "int_8s"
	}
	constraints = "PRIMARY KEY (event_id)"
	next_id = SnglRingdownID(0)
	interncolumns = ("ifo", "channel")


class SnglRingdown(table.Table.RowType):
	__slots__ = tuple(map(table.Column.ColumnName, SnglRingdownTable.validcolumns))

	start = gpsproperty_with_gmst("start_time", "start_time_ns", "start_time_gmst")


SnglRingdownTable.RowType = SnglRingdown


#
# =============================================================================
#
#                             coinc_ringdown:table
#
# =============================================================================
#


class CoincRingdownTable(table.Table):
	tableName = "coinc_ringdown"
	validcolumns = {
		"coinc_event:coinc_event_id": "int_8s",
		"ifos": "lstring",
		"start_time": "int_4s",
		"start_time_ns": "int_4s",
		"frequency": "real_8",
		"quality": "real_8",
		"mass": "real_8",
		"spin": "real_8",
		"snr": "real_8",
		"choppedl_snr": "real_8",
		"snr_sq": "real_8",
		"eff_coh_snr": "real_8",
		"null_stat": "real_8",
		"kappa": "real_8",
		"snr_ratio": "real_8",
		"false_alarm_rate": "real_8",
		"combined_far": "real_8"
	}
	# constraints = "PRIMARY KEY (coinc_event_id)"
	how_to_index = {
		"cr_cei_index": ("coinc_event_id",)
	}
	interncolumns = ("ifos",)


class CoincRingdown(table.Table.RowType):
	__slots__ = tuple(map(table.Column.ColumnName, CoincRingdownTable.validcolumns))

	instruments = instrumentsproperty("ifos")

	start = gpsproperty("start_time", "start_time_ns")


CoincRingdownTable.RowType = CoincRingdown


#
# =============================================================================
#
#                              sim_inspiral:table
#
# =============================================================================
#


SimInspiralID = table.next_id.type(u"simulation_id")


class SimInspiralTable(table.Table):
	tableName = "sim_inspiral"
	validcolumns = {
		"process:process_id": "int_8s",
		"waveform": "lstring",
		"geocent_end_time": "int_4s",
		"geocent_end_time_ns": "int_4s",
		"h_end_time": "int_4s",
		"h_end_time_ns": "int_4s",
		"l_end_time": "int_4s",
		"l_end_time_ns": "int_4s",
		"g_end_time": "int_4s",
		"g_end_time_ns": "int_4s",
		"t_end_time": "int_4s",
		"t_end_time_ns": "int_4s",
		"v_end_time": "int_4s",
		"v_end_time_ns": "int_4s",
		"end_time_gmst": "real_8",
		"source": "lstring",
		"mass1": "real_4",
		"mass2": "real_4",
		"mchirp": "real_4",
		"eta": "real_4",
		"distance": "real_4",
		"longitude": "real_4",
		"latitude": "real_4",
		"inclination": "real_4",
		"coa_phase": "real_4",
		"polarization": "real_4",
		"psi0": "real_4",
		"psi3": "real_4",
		"alpha": "real_4",
		"alpha1": "real_4",
		"alpha2": "real_4",
		"alpha3": "real_4",
		"alpha4": "real_4",
		"alpha5": "real_4",
		"alpha6": "real_4",
		"beta": "real_4",
		"spin1x": "real_4",
		"spin1y": "real_4",
		"spin1z": "real_4",
		"spin2x": "real_4",
		"spin2y": "real_4",
		"spin2z": "real_4",
		"theta0": "real_4",
		"phi0": "real_4",
		"f_lower": "real_4",
		"f_final": "real_4",
		"eff_dist_h": "real_4",
		"eff_dist_l": "real_4",
		"eff_dist_g": "real_4",
		"eff_dist_t": "real_4",
		"eff_dist_v": "real_4",
		"numrel_mode_min": "int_4s",
		"numrel_mode_max": "int_4s",
		"numrel_data": "lstring",
		"amp_order": "int_4s",
		"taper": "lstring",
		"bandpass": "int_4s",
		"simulation_id": "int_8s"
	}
	constraints = "PRIMARY KEY (simulation_id)"
	next_id = SimInspiralID(0)
	interncolumns = ("waveform", "source")


class SimInspiral(table.Table.RowType):
	"""
	Example:

	>>> x = SimInspiral()
	>>> x.ra_dec = 0., 0.
	>>> x.ra_dec
	(0.0, 0.0)
	>>> x.ra_dec = None
	>>> print(x.ra_dec)
	None
	>>> x.time_geocent = None
	>>> print(x.time_geocent)
	None
	>>> print(x.end_time_gmst)
	None
	>>> x.time_geocent = LIGOTimeGPS(6e8)
	>>> print(x.time_geocent)
	600000000
	>>> print(x.end_time_gmst)
	-2238.39417156
	"""
	__slots__ = tuple(map(table.Column.ColumnName, SimInspiralTable.validcolumns))

	time_geocent = gpsproperty_with_gmst("geocent_end_time", "geocent_end_time_ns", "end_time_gmst")

	@property
	def ra_dec(self):
		if self.longitude is None and self.latitude is None:
			return None
		return self.longitude, self.latitude

	@ra_dec.setter
	def ra_dec(self, radec):
		if radec is None:
			self.longitude = self.latitude = None
		else:
			self.longitude, self.latitude = radec

	@property
	def spin1(self):
		if self.spin1x is None and self.spin1y is None and self.spin1z is None:
			return None
		return numpy.array((self.spin1x, self.spin1y, self.spin1z), dtype = "double")

	@spin1.setter
	def spin1(self, spin):
		if spin is None:
			self.spin1x, self.spin1y, self.spin1z = None, None, None
		else:
			self.spin1x, self.spin1y, self.spin1z = spin

	@property
	def spin2(self):
		if self.spin2x is None and self.spin2y is None and self.spin2z is None:
			return None
		return numpy.array((self.spin2x, self.spin2y, self.spin2z), dtype = "double")

	@spin2.setter
	def spin2(self, spin):
		if spin is None:
			self.spin2x, self.spin2y, self.spin2z = None, None, None
		else:
			self.spin2x, self.spin2y, self.spin2z = spin

	def time_at_instrument(self, instrument, offsetvector):
		"""
		Return the "time" of the injection, delay corrected for the
		displacement from the geocentre to the given instrument.

		NOTE:  this method does not account for the rotation of the
		Earth that occurs during the transit of the plane wave from
		the detector to the geocentre.  That is, it is assumed the
		Earth is in the same orientation with respect to the
		celestial sphere when the wave passes through the detector
		as when it passes through the geocentre.  The Earth rotates
		by about 1.5 urad during the 21 ms it takes light to travel
		the radius of the Earth, which corresponds to 10 m of
		displacement at the equator, or 33 light-ns.  Therefore,
		the failure to do a proper retarded time calculation here
		results in errors as large as 33 ns.  This is insignificant
		for burst searches, but be aware that this approximation is
		being made if the return value is used in other contexts.
		"""
		# the offset is subtracted from the time of the injection.
		# injections are done this way so that when the triggers
		# that result from an injection have the offset vector
		# added to their times the triggers will form a coinc
		t_geocent = self.time_geocent - offsetvector[instrument]
		ra, dec = self.ra_dec
		return t_geocent + lal.TimeDelayFromEarthCenter(lal.cached_detector_by_prefix[instrument].location, ra, dec, t_geocent)


SimInspiralTable.RowType = SimInspiral


#
# =============================================================================
#
#                               sim_burst:table
#
# =============================================================================
#


SimBurstID = table.next_id.type(u"simulation_id")


class SimBurstTable(table.Table):
	tableName = "sim_burst"
	validcolumns = {
		"process:process_id": "int_8s",
		"waveform": "lstring",
		"ra": "real_8",
		"dec": "real_8",
		"psi": "real_8",
		"time_geocent_gps": "int_4s",
		"time_geocent_gps_ns": "int_4s",
		"time_geocent_gmst": "real_8",
		"duration": "real_8",
		"frequency": "real_8",
		"bandwidth": "real_8",
		"q": "real_8",
		"pol_ellipse_angle": "real_8",
		"pol_ellipse_e": "real_8",
		"amplitude": "real_8",
		"hrss": "real_8",
		"egw_over_rsquared": "real_8",
		"waveform_number": "int_8u",
		"time_slide:time_slide_id": "int_8s",
		"simulation_id": "int_8s"
	}
	constraints = "PRIMARY KEY (simulation_id)"
	next_id = SimBurstID(0)
	interncolumns = ("waveform",)


class SimBurst(table.Table.RowType):
	"""
	Example:

	>>> x = SimBurst()
	>>> x.ra_dec = 0., 0.
	>>> x.ra_dec
	(0.0, 0.0)
	>>> x.ra_dec = None
	>>> print(x.ra_dec)
	None
	>>> x.time_geocent = None
	>>> print(x.time_geocent)
	None
	>>> print(x.time_geocent_gmst)
	None
	>>> x.time_geocent = LIGOTimeGPS(6e8)
	>>> print(x.time_geocent)
	600000000
	>>> print(x.time_geocent_gmst)
	-2238.39417156
	"""
	__slots__ = tuple(map(table.Column.ColumnName, SimBurstTable.validcolumns))

	time_geocent = gpsproperty_with_gmst("time_geocent_gps", "time_geocent_gps_ns", "time_geocent_gmst")

	@property
	def ra_dec(self):
		if self.ra is None and self.dec is None:
			return None
		return self.ra, self.dec

	@ra_dec.setter
	def ra_dec(self, radec):
		if radec is None:
			self.ra = self.dec = None
		else:
			self.ra, self.dec = radec

	def time_at_instrument(self, instrument, offsetvector):
		"""
		Return the "time" of the injection, delay corrected for the
		displacement from the geocentre to the given instrument.

		NOTE:  this method does not account for the rotation of the
		Earth that occurs during the transit of the plane wave from
		the detector to the geocentre.  That is, it is assumed the
		Earth is in the same orientation with respect to the
		celestial sphere when the wave passes through the detector
		as when it passes through the geocentre.  The Earth rotates
		by about 1.5 urad during the 21 ms it takes light to travel
		the radius of the Earth, which corresponds to 10 m of
		displacement at the equator, or 33 light-ns.  Therefore,
		the failure to do a proper retarded time calculation here
		results in errors as large as 33 ns.  This is insignificant
		for burst searches, but be aware that this approximation is
		being made if the return value is used in other contexts.
		"""
		# the offset is subtracted from the time of the injection.
		# injections are done this way so that when the triggers
		# that result from an injection have the offset vector
		# added to their times the triggers will form a coinc
		t_geocent = self.time_geocent - offsetvector[instrument]
		ra, dec = self.ra_dec
		return t_geocent + lal.TimeDelayFromEarthCenter(lal.cached_detector_by_prefix[instrument].location, ra, dec, t_geocent)


SimBurstTable.RowType = SimBurst


#
# =============================================================================
#
#                              sim_ringdown:table
#
# =============================================================================
#


SimRingdownID = table.next_id.type(u"simulation_id")


class SimRingdownTable(table.Table):
	tableName = "sim_ringdown"
	validcolumns = {
		"process:process_id": "int_8s",
		"waveform": "lstring",
		"coordinates": "lstring",
		"geocent_start_time": "int_4s",
		"geocent_start_time_ns": "int_4s",
		"h_start_time": "int_4s",
		"h_start_time_ns": "int_4s",
		"l_start_time": "int_4s",
		"l_start_time_ns": "int_4s",
		"v_start_time": "int_4s",
		"v_start_time_ns": "int_4s",
		"start_time_gmst": "real_8",
		"longitude": "real_4",
		"latitude": "real_4",
		"distance": "real_4",
		"inclination": "real_4",
		"polarization": "real_4",
		"frequency": "real_4",
		"quality": "real_4",
		"phase": "real_4",
		"mass": "real_4",
		"spin": "real_4",
		"epsilon": "real_4",
		"amplitude": "real_4",
		"eff_dist_h": "real_4",
		"eff_dist_l": "real_4",
		"eff_dist_v": "real_4",
		"hrss": "real_4",
		"hrss_h": "real_4",
		"hrss_l": "real_4",
		"hrss_v": "real_4",
		"simulation_id": "int_8s"
	}
	constraints = "PRIMARY KEY (simulation_id)"
	next_id = SimRingdownID(0)
	interncolumns = ("waveform", "coordinates")


class SimRingdown(table.Table.RowType):
	__slots__ = tuple(map(table.Column.ColumnName, SimRingdownTable.validcolumns))

	geocent_start = gpsproperty_with_gmst("geocent_start_time", "geocent_start_time_ns", "start_time_gmst")

	@property
	def ra_dec(self):
		if self.longitude is None and self.latitude is None:
			return None
		return self.longitude, self.latitude

	@ra_dec.setter
	def ra_dec(self, radec):
		if radec is None:
			self.longitude = self.latitude = None
		else:
			self.longitude, self.latitude = radec

	def time_at_instrument(self, instrument, offsetvector):
		"""
		Return the start time of the injection, delay corrected for
		the displacement from the geocentre to the given
		instrument.

		NOTE:  this method does not account for the rotation of the
		Earth that occurs during the transit of the plane wave from
		the detector to the geocentre.  That is, it is assumed the
		Earth is in the same orientation with respect to the
		celestial sphere when the wave passes through the detector
		as when it passes through the geocentre.  The Earth rotates
		by about 1.5 urad during the 21 ms it takes light to travel
		the radius of the Earth, which corresponds to 10 m of
		displacement at the equator, or 33 light-ns.  Therefore,
		the failure to do a proper retarded time calculation here
		results in errors as large as 33 ns.  This is insignificant
		for ring-down searches, but be aware that this
		approximation is being made if the return value is used in
		other contexts.
		"""
		# the offset is subtracted from the time of the injection.
		# injections are done this way so that when the triggers
		# that result from an injection have the offset vector
		# added to their times the triggers will form a coinc
		t_geocent = self.geocent_start - offsetvector[instrument]
		ra, dec = self.ra_dec
		return t_geocent + lal.TimeDelayFromEarthCenter(lal.cached_detector_by_prefix[instrument].location, ra, dec, t_geocent)


SimRingdownTable.RowType = SimRingdown


#
# =============================================================================
#
#                               summ_value:table
#
# =============================================================================
#


SummValueID = table.next_id.type(u"summ_value_id")


class SummValueTable(table.Table):
	tableName = "summ_value"
	validcolumns = {
		"summ_value_id": "int_8s",
		"program": "lstring",
		"process:process_id": "int_8s",
		"frameset_group": "lstring",
		"segment_definer:segment_def_id": "int_8s",
		"start_time": "int_4s",
		"start_time_ns": "int_4s",
		"end_time": "int_4s",
		"end_time_ns": "int_4s",
		"ifo": "lstring",
		"name": "lstring",
		"value": "real_4",
		"error": "real_4",
		"intvalue": "int_4s",
		"comment": "lstring"
	}
	constraints = "PRIMARY KEY (summ_value_id)"
	next_id = SummValueID(0)
	interncolumns = ("program", "ifo", "name", "comment")


class SummValue(table.Table.RowType):
	"""
	Example:

	>>> x = SummValue()
	>>> x.instruments = (u"H1", u"L1")
	>>> x.ifo
	u'H1,L1'
	>>> x.instruments
	set([u'H1', u'L1'])
	>>> x.start = LIGOTimeGPS(0)
	>>> x.end = LIGOTimeGPS(10)
	>>> x.segment
	segment(LIGOTimeGPS(0, 0), LIGOTimeGPS(10, 0))
	>>> x.segment = None
	>>> print(x.segment)
	None
	"""
	__slots__ = tuple(map(table.Column.ColumnName, SummValueTable.validcolumns))

	instruments = instrumentsproperty("ifo")

	start = gpsproperty("start_time", "start_time_ns")
	end = gpsproperty("end_time", "end_time_ns")
	segment = segmentproperty("start", "end")


SummValueTable.RowType = SummValue


#
# =============================================================================
#
#                                segment:table
#
# =============================================================================
#


SegmentID = table.next_id.type(u"segment_id")


class SegmentTable(table.Table):
	tableName = "segment"
	validcolumns = {
		"creator_db": "int_4s",
		"process:process_id": "int_8s",
		"segment_id": "int_8s",
		"start_time": "int_4s",
		"start_time_ns": "int_4s",
		"end_time": "int_4s",
		"end_time_ns": "int_4s",
		"segment_definer:segment_def_id": "int_8s",
		"segment_def_cdb": "int_4s"
	}
	constraints = "PRIMARY KEY (segment_id)"
	next_id = SegmentID(0)


class Segment(table.Table.RowType):
	"""
	Example:

	>>> x = Segment()
	>>> x.start = LIGOTimeGPS(0)
	>>> x.end = LIGOTimeGPS(10)
	>>> x.segment
	segment(LIGOTimeGPS(0, 0), LIGOTimeGPS(10, 0))
	>>> x.segment = None
	>>> print(x.segment)
	None
	>>> print(x.start)
	None
	>>> # non-LIGOTimeGPS times are converted to LIGOTimeGPS
	>>> x.segment = (20, 30.125)
	>>> x.end
	LIGOTimeGPS(30, 125000000)
	>>> # initialization from a tuple or with arguments
	>>> Segment((20, 30)).segment
	segment(LIGOTimeGPS(20, 0), LIGOTimeGPS(30, 0))
	>>> Segment(20, 30).segment
	segment(LIGOTimeGPS(20, 0), LIGOTimeGPS(30, 0))
	>>> # use as a segment object in segmentlist operations
	>>> from glue import segments
	>>> x = segments.segmentlist([Segment(0, 10), Segment(20, 30)])
	>>> abs(x)
	LIGOTimeGPS(20, 0)
	>>> y = segments.segmentlist([Segment(5, 15), Segment(25, 35)])
	>>> abs(x & y)
	LIGOTimeGPS(10, 0)
	>>> abs(x | y)
	LIGOTimeGPS(30, 0)
	>>> 8.0 in x
	True
	>>> 12 in x
	False
	>>> Segment(2, 3) in x
	True
	>>> Segment(2, 12) in x
	False
	>>> segments.segment(2, 3) in x
	True
	>>> segments.segment(2, 12) in x
	False
	>>> # make sure results are segment table row objects
	>>> segments.segmentlist(map(Segment, x & y))	# doctest: +ELLIPSIS
	[<ligo.lw.lsctables.Segment object at 0x...>, <ligo.lw.lsctables.Segment object at 0x...>]

	This implementation uses a non-standard extension to encode
	infinite values for boundaries:  the second and nanosecond
	components are both set to 0x7FFFFFFF or 0xFFFFFFFF to indicate
	positive resp. negative infinity.  For this reason, "denormalized"
	LIGOTimeGPS objects (objects whose nanoseconds fields contain
	values exceeding +/-999999999) are disallowed for use with this
	class.

	Example:

	>>> x = Segment()
	>>> # OK
	>>> x.start = -segments.infinity()
	>>> # also OK
	>>> x.start = float("-inf")
	>>> # infinite boundaries always returned as segments.infinity
	>>> # instances
	>>> x.start
	-infinity
	>>> x.end = float("+inf")
	>>> x.segment
	segment(-infinity, infinity)
	"""
	__slots__ = tuple(map(table.Column.ColumnName, SegmentTable.validcolumns))

	start = gpsproperty("start_time", "start_time_ns")
	end = gpsproperty("end_time", "end_time_ns")
	segment = segmentproperty("start", "end")

	# emulate a glue.segments.segment object

	def __abs__(self):
		return abs(self.segment)

	def __cmp__(self, other):
		return cmp(self.segment, other)

	def __contains__(self, other):
		return other in self.segment

	def __getitem__(self, i):
		return self.segment[i]

	def __init__(self, *args, **kwargs):
		if args:
			try:
				# first try unpacking arguments
				self.segment = args
			except ValueError:
				# didn't work, try unpacking 0th argument
				self.segment, = args
		for key, value in kwargs.items():
			setattr(self, key, value)

	def __len__(self):
		return len(self.segment)

	def __nonzero__(self):
		return bool(self.segment)


SegmentTable.RowType = Segment


#
# =============================================================================
#
#                            segment_definer:table
#
# =============================================================================
#


SegmentDefID = table.next_id.type(u"segment_def_id")


class SegmentDefTable(table.Table):
	tableName = "segment_definer"
	validcolumns = {
		"creator_db": "int_4s",
		"process:process_id": "int_8s",
		"segment_def_id": "int_8s",
		"ifos": "lstring",
		"name": "lstring",
		"version": "int_4s",
		"comment": "lstring",
		"insertion_time": "int_4s"
	}
	constraints = "PRIMARY KEY (segment_def_id)"
	next_id = SegmentDefID(0)


class SegmentDef(table.Table.RowType):
	"""
	Example:

	>>> x = SegmentDef()
	>>> x.instruments = (u"H1", u"L1")
	>>> x.ifos
	u'H1,L1'
	>>> x.instruments
	set([u'H1', u'L1'])
	"""
	__slots__ = tuple(map(table.Column.ColumnName, SegmentDefTable.validcolumns))

	instruments = instrumentsproperty("ifos")


SegmentDefTable.RowType = SegmentDef


#
# =============================================================================
#
#                            segment_summary:table
#
# =============================================================================
#


SegmentSumID = table.next_id.type(u"segment_sum_id")


class SegmentSumTable(table.Table):
	tableName = "segment_summary"
	validcolumns = {
		"creator_db": "int_4s",
		"process:process_id": "int_8s",
		"segment_sum_id": "int_8s",
		"start_time": "int_4s",
		"start_time_ns": "int_4s",
		"end_time": "int_4s",
		"end_time_ns": "int_4s",
		"comment": "lstring",
		"segment_definer:segment_def_id": "int_8s",
		"segment_def_cdb": "int_4s"
	}
	constraints = "PRIMARY KEY (segment_sum_id)"
	next_id = SegmentSumID(0)

	def get(self, segment_def_id = None):
		"""
		Return a segmentlist object describing the times spanned by
		the segments carrying the given segment_def_id.  If
		segment_def_id is None then all segments are returned.

		Note:  the result is not coalesced, the segmentlist
		contains the segments as they appear in the table.
		"""
		if segment_def_id is None:
			return segments.segmentlist(row.segment for row in self)
		return segments.segmentlist(row.segment for row in self if row.segment_def_id == segment_def_id)


class SegmentSum(Segment):
	__slots__ = tuple(map(table.Column.ColumnName, SegmentSumTable.validcolumns))


SegmentSumTable.RowType = SegmentSum


#
# =============================================================================
#
#                               time_slide:table
#
# =============================================================================
#


TimeSlideID = table.next_id.type(u"time_slide_id")


class TimeSlideTable(table.Table):
	tableName = "time_slide"
	validcolumns = {
		"process:process_id": "int_8s",
		"time_slide_id": "int_8s",
		"instrument": "lstring",
		"offset": "real_8"
	}
	constraints = "PRIMARY KEY (time_slide_id, instrument)"
	next_id = TimeSlideID(0)
	interncolumns = ("instrument",)

	def as_dict(self):
		"""
		Return a ditionary mapping time slide IDs to offset
		dictionaries.

		NOTE:  very little checking is done, e.g., for repeated
		instruments for a given ID (which could suggest an ID
		collision).
		"""
		return dict((time_slide_id, offsetvector((row.instrument, row.offset) for row in rows)) for time_slide_id, rows in itertools.grouby(sorted(self, lambda row: row.time_slide_id), lambda row: row.time_slide_id))

	def append_offsetvector(self, offsetvect, process):
		"""
		Append rows describing an instrument --> offset mapping to
		this table.  offsetvect is a dictionary mapping instrument
		to offset.  process should be the row in the process table
		on which the new time_slide table rows will be blamed (or
		any object with a process_id attribute).  The return value
		is the time_slide_id assigned to the new rows.
		"""
		time_slide_id = self.get_next_id()
		for instrument, offset in offsetvect.items():
			self.append(self.RowType(
				process_id = process.process_id,
				time_slide_id = time_slide_id,
				instrument = instrument,
				offset = offset
			))
		return time_slide_id

	def get_time_slide_id(self, offsetdict, create_new = None, superset_ok = False, nonunique_ok = False):
		"""
		Return the time_slide_id corresponding to the offset vector
		described by offsetdict, a dictionary of instrument/offset
		pairs.

		If the optional create_new argument is None (the default),
		then the table must contain a matching offset vector.  The
		return value is the ID of that vector.  If the table does
		not contain a matching offset vector then KeyError is
		raised.

		If the optional create_new argument is set to a Process
		object (or any other object with a process_id attribute),
		then if the table does not contain a matching offset vector
		a new one will be added to the table and marked as having
		been created by the given process.  The return value is the
		ID of the (possibly newly created) matching offset vector.

		If the optional superset_ok argument is False (the default)
		then an offset vector in the table is considered to "match"
		the requested offset vector only if they contain the exact
		same set of instruments.  If the superset_ok argument is
		True, then an offset vector in the table is considered to
		match the requested offset vector as long as it provides
		the same offsets for the same instruments as the requested
		vector, even if it provides offsets for other instruments
		as well.

		More than one offset vector in the table might match the
		requested vector.  If the optional nonunique_ok argument is
		False (the default), then KeyError will be raised if more
		than one offset vector in the table is found to match the
		requested vector.  If the optional nonunique_ok is True
		then the return value is the ID of one of the matching
		offset vectors selected at random.
		"""
		# look for matching offset vectors
		if superset_ok:
			ids = [time_slide_id for time_slide_idid, slide in self.as_dict().items() if offsetdict == dict((instrument, offset) for instrument, offset in slide.items() if instrument in offsetdict)]
		else:
			ids = [time_slide_id for time_slide_id, slide in self.as_dict().items() if offsetdict == slide]
		if len(ids) > 1:
			# found more than one
			if nonunique_ok:
				# and that's OK
				return ids[0]
			# and that's not OK
			raise KeyError("%s not unique" % repr(offsetdict))
		if len(ids) == 1:
			# found one
			return ids[0]
		# offset vector not found in table
		if create_new is None:
			# and that's not OK
			raise KeyError("%s not found" % repr(offsetdict))
		# that's OK, create new vector, return its ID
		return self.append_offsetvector(offsetdict, create_new)


class TimeSlide(table.Table.RowType):
	__slots__ = tuple(map(table.Column.ColumnName, TimeSlideTable.validcolumns))


TimeSlideTable.RowType = TimeSlide


#
# =============================================================================
#
#                             coinc_definer:table
#
# =============================================================================
#


CoincDefID = table.next_id.type(u"coinc_def_id")


class CoincDefTable(table.Table):
	tableName = "coinc_definer"
	validcolumns = {
		"coinc_def_id": "int_8s",
		"search": "lstring",
		"search_coinc_type": "int_4u",
		"description": "lstring"
	}
	constraints = "PRIMARY KEY (coinc_def_id)"
	next_id = CoincDefID(0)
	how_to_index = {
		"cd_ssct_index": ("search", "search_coinc_type")
	}

	def get_coinc_def_id(self, search, search_coinc_type, create_new = True, description = None):
		"""
		Return the coinc_def_id for the row in the table whose
		search string and search_coinc_type integer have the values
		given.  If a matching row is not found, the default
		behaviour is to create a new row and return the ID assigned
		to the new row.  If, instead, create_new is False then
		KeyError is raised when a matching row is not found.  The
		optional description parameter can be used to set the
		description string assigned to the new row if one is
		created, otherwise the new row is left with no description.
		"""
		# look for the ID
		rows = [row for row in self if (row.search, row.search_coinc_type) == (search, search_coinc_type)]
		if len(rows) > 1:
			raise ValueError("(search, search coincidence type) = ('%s', %d) is not unique" % (search, search_coinc_type))
		if len(rows) > 0:
			return rows[0].coinc_def_id

		# coinc type not found in table
		if not create_new:
			raise KeyError((search, search_coinc_type))
		coinc_def_id = self.get_next_id(),
		self.append(self.RowType(
			coinc_def_id = coinc_def_id,
			search = search,
			search_coinc_type = search_coinc_type,
			description = description
		))

		# return new ID
		return coinc_def_id


class CoincDef(table.Table.RowType):
	__slots__ = tuple(map(table.Column.ColumnName, CoincDefTable.validcolumns))


CoincDefTable.RowType = CoincDef


#
# =============================================================================
#
#                              coinc_event:table
#
# =============================================================================
#


CoincID = table.next_id.type(u"coinc_event_id")


class CoincTable(table.Table):
	tableName = "coinc_event"
	validcolumns = {
		"process:process_id": "int_8s",
		"coinc_definer:coinc_def_id": "int_8s",
		"coinc_event_id": "int_8s",
		"time_slide:time_slide_id": "int_8s",
		"instruments": "lstring",
		"nevents": "int_4u",
		"likelihood": "real_8"
	}
	constraints = "PRIMARY KEY (coinc_event_id)"
	next_id = CoincID(0)
	interncolumns = ("instruments",)
	how_to_index = {
		"ce_cdi_index": ("coinc_def_id",),
		"ce_tsi_index": ("time_slide_id",)
	}


class Coinc(table.Table.RowType):
	__slots__ = tuple(map(table.Column.ColumnName, CoincTable.validcolumns))

	insts = instrumentsproperty("instruments")


CoincTable.RowType = Coinc


#
# =============================================================================
#
#                            coinc_event_map:table
#
# =============================================================================
#


class CoincMapTable(table.Table):
	tableName = "coinc_event_map"
	validcolumns = {
		"coinc_event:coinc_event_id": "int_8s",
		"table_name": "char_v",
		"event_id": "int_8s"
	}
	interncolumns = ("table_name",)
	how_to_index = {
		"cem_tn_ei_index": ("table_name", "event_id"),
		"cem_cei_index": ("coinc_event_id",)
	}

	def applyKeyMapping(self, mapping):
		table_column = self.getColumnByName("table_name")
		event_id_column = self.getColumnByName("event_id")
		coinc_event_id_column = self.getColumnByName("coinc_event_id")
		for i, (table_name, old_event_id, old_coinc_event_id) in enumerate(zip(table_column, event_id_column, coinc_event_id_column)):
			try:
				event_id_column[i] = mapping[table_name, old_event_id]
			except KeyError:
				pass
			try:
				coinc_event_id_column[i] = mapping["coinc_event", old_coinc_event_id]
			except KeyError:
				pass


class CoincMap(table.Table.RowType):
	__slots__ = tuple(map(table.Column.ColumnName, CoincMapTable.validcolumns))


CoincMapTable.RowType = CoincMap


#
# =============================================================================
#
#                                dq_list Table
#
# =============================================================================
#


DQSpecListID = table.next_id.type(u"dq_list_id")
DQSpecListRowID = table.next_id.type(u"dq_list_row_id")


class DQSpecListTable(table.Table):
	tableName = "dq_list"
	validcolumns = {
		"dq_list:dq_list_id": "int_8s",
		"dq_list_row_id": "int_8s",
		"instrument": "lstring",
		"flag": "lstring",
		"low_window": "real_8",
		"high_window": "real_8"
	}
	constraints = "PRIMARY KEY (dq_list_id, dq_list_row_id)"
	next_id = DQSpecListID(0)


class DQSpec(table.Table.RowType):
	__slots__ = tuple(map(table.Column.ColumnName, DQSpecListTable.validcolumns))

	def apply_to_segmentlist(self, seglist):
		"""
		Apply our low and high windows to the segments in a
		segmentlist.
		"""
		for i, seg in enumerate(seglist):
			seglist[i] = seg.__class__(seg[0] - self.low_window, seg[1] + self.high_window)


DQSpecListTable.RowType = DQSpec


#
# =============================================================================
#
#                            veto_definer:table
#
# =============================================================================
#


class VetoDefTable(table.Table):
	tableName = "veto_definer"
	validcolumns = {
		"process:process_id": "int_8s",
		"ifo": "lstring",
		"name": "lstring",
		"version": "int_4s",
		"category": "int_4s",
		"start_time": "int_4s",
		"end_time": "int_4s",
		"start_pad": "int_4s",
		"end_pad": "int_4s",
		"comment": "lstring"
	}
	interncolumns = ("ifo",)


class VetoDef(table.Table.RowType):
	__slots__ = tuple(map(table.Column.ColumnName, VetoDefTable.validcolumns))


VetoDefTable.RowType = VetoDef


#
# =============================================================================
#
#                                Table Metadata
#
# =============================================================================
#


#
# Table name ---> table type mapping.
#


TableByName = {
	CoincDefTable.tableName: CoincDefTable,
	CoincInspiralTable.tableName: CoincInspiralTable,
	CoincMapTable.tableName: CoincMapTable,
	CoincRingdownTable.tableName: CoincRingdownTable,
	CoincTable.tableName: CoincTable,
	DQSpecListTable.tableName: DQSpecListTable,
	ExperimentMapTable.tableName: ExperimentMapTable,
	ExperimentSummaryTable.tableName: ExperimentSummaryTable,
	ExperimentTable.tableName: ExperimentTable,
	ProcessParamsTable.tableName: ProcessParamsTable,
	ProcessTable.tableName: ProcessTable,
	SearchSummaryTable.tableName: SearchSummaryTable,
	SearchSummVarsTable.tableName: SearchSummVarsTable,
	SegmentDefTable.tableName: SegmentDefTable,
	SegmentSumTable.tableName: SegmentSumTable,
	SegmentTable.tableName: SegmentTable,
	SimBurstTable.tableName: SimBurstTable,
	SimInspiralTable.tableName: SimInspiralTable,
	SimRingdownTable.tableName: SimRingdownTable,
	SnglBurstTable.tableName: SnglBurstTable,
	SnglInspiralTable.tableName: SnglInspiralTable,
	SnglRingdownTable.tableName: SnglRingdownTable,
	SummValueTable.tableName: SummValueTable,
	TimeSlideTable.tableName: TimeSlideTable,
	VetoDefTable.tableName: VetoDefTable
}


def reset_next_ids(classes):
	"""
	For each class in the list, if the .next_id attribute is not None
	(meaning the table has an ID generator associated with it), set
	.next_id to 0.  This has the effect of reseting the ID generators,
	and is useful in applications that process multiple documents and
	add new rows to tables in those documents.  Calling this function
	between documents prevents new row IDs from growing continuously
	from document to document.  There is no need to do this, it's
	purpose is merely aesthetic, but it can be confusing to open a
	document and find process ID 300 in the process table and wonder
	what happened to the other 299 processes.

	Example:

	>>> reset_next_ids(TableByName.values())
	"""
	for cls in classes:
		cls.reset_next_id()


#
# =============================================================================
#
#                               Content Handler
#
# =============================================================================
#


#
# Override portions of a ligolw.LIGOLWContentHandler class
#


def use_in(ContentHandler):
	"""
	Modify ContentHandler, a sub-class of
	ligo.lw.ligolw.LIGOLWContentHandler, to cause it to use the Table
	classes defined in this module when parsing XML documents.

	Example:

	>>> from ligo.lw import ligolw
	>>> class MyContentHandler(ligolw.LIGOLWContentHandler):
	...	pass
	...
	>>> use_in(MyContentHandler)
	<class 'ligo.lw.lsctables.MyContentHandler'>
	"""
	ContentHandler = table.use_in(ContentHandler)

	def startTable(self, parent, attrs, __orig_startTable = ContentHandler.startTable):
		name = table.Table.TableName(attrs[u"Name"])
		if name in TableByName:
			return TableByName[name](attrs)
		return __orig_startTable(self, parent, attrs)

	ContentHandler.startTable = startTable

	return ContentHandler
