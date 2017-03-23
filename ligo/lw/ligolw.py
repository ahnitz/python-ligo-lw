# Copyright (C) 2006--2016  Kipp Cannon
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
This module provides class definitions corresponding to the elements that
can be found in a LIGO Light Weight XML file.  It also provides a class
representing an entire LIGO Light Weight XML document, a ContentHandler
class for use with SAX2 parsers, and a convenience function for
constructing a parser.
"""


import sys
from xml import sax
from xml.sax.xmlreader import AttributesImpl
from xml.sax.saxutils import escape as xmlescape
from xml.sax.saxutils import unescape as xmlunescape


from . import __author__, __date__, __version__
from . import types as ligolwtypes
import six
from functools import reduce


#
# =============================================================================
#
#                         Document Header, and Indent
#
# =============================================================================
#


NameSpace = u"http://ldas-sw.ligo.caltech.edu/doc/ligolwAPI/html/ligolw_dtd.txt"


Header = u"""<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE LIGO_LW SYSTEM "%s">""" % NameSpace


Indent = u"\t"


#
# =============================================================================
#
#                                Element Class
#
# =============================================================================
#


class ElementError(Exception):
	"""
	Base class for exceptions generated by elements.
	"""
	pass


class attributeproxy(property):
	"""
	Expose an XML attribute of an Element subclass as Python instance
	attribute with support for an optional default value.

	The .getAttribute() and .setAttribute() methods of the instance to
	which this is attached are used to retrieve and set the unicode
	attribute value, respectively.

	When retrieving a value, the function given via the dec keyword
	argument will be used to convert the unicode into a native Python
	object (the default is to leave the unicode value as unicode).
	When setting a value, the function given via the enc keyword
	argument will be used to convert a native Python object to a
	unicode string.

	When retrieving a value, if .getAttribute() raises KeyError then
	AttributeError is raised unless a default value is provided in
	which case it is returned instead.

	If doc is provided it will be used as the documentation string,
	otherwise a default documentation string will be constructed
	identifying the attribute's name and explaining the default value
	if one is set.

	NOTE:  If an XML document is parsed and an element is encountered
	that does not have a value set for an attribute whose corresponding
	attributeproxy has a default value defined, then Python codes will
	be told the default value.  Therefore, the default value given here
	must match what the XML DTD says the default value is for that
	attribute.  Likewise, attributes for which the DTD does not define
	a default must not have a default defined here.  These conditions
	must both be met to not create a discrepancy between the behaviour
	of Python codes relying on this I/O library and other interfaces to
	the same document.

	Example:

	>>> class Test(Element):
	...	Scale = attributeproxy(u"Scale", enc = u"%.17g".__mod__, dec = float, default = 1.0, doc = "This is the scale (default = 1).")
	...
	>>> x = Test()
	>>> # have not set value, default will be returned
	>>> x.Scale
	1.0
	>>> x.Scale = 16
	>>> x.Scale
	16.0
	>>> # default can be retrieved via the .default attribute of the
	>>> # class attribute
	>>> Test.Scale.default
	1.0
	>>> # default is read-only
	>>> Test.Scale.default = 2.
	Traceback (most recent call last):
	  File "<stdin>", line 1, in <module>
	AttributeError: can't set attribute
	>>> # internally, value is stored as unicode (for XML)
	>>> x.getAttribute("Scale")
	u'16'
	>>> # deleting an attribute restores the default value if defined
	>>> del x.Scale
	>>> x.Scale
	1.0
	"""
	def __init__(self, name, enc = six.text_type, dec = six.text_type, default = None, doc = None):
		# define get/set/del implementations, relying on Python's
		# closure mechanism to remember values for name, default,
		# etc.
		def getter(self):
			try:
				val = self.getAttribute(name)
			except KeyError:
				if default is not None:
					return default
				raise AttributeError("attribute '%s' is not set" % name)
			return dec(val)
		def setter(self, value):
			self.setAttribute(name, enc(value))
		def deleter(self):
			self.removeAttribute(name)
		# construct a default documentation string if needed
		if doc is None:
			doc = "The \"%s\" attribute." % name
			if default is not None:
				doc += "  Default is \"%s\" if not set." % str(default)
		# initialize the property object
		super(attributeproxy, self).__init__(getter, (setter if enc is not None else None), (deleter if enc is not None else None), doc)
		# documentation is not inherited, need to set it explicitly
		self.__doc__ = doc
		# record default attribute.  if no value is supplied,
		# AttributeError will be raised on attempts to retrieve it
		if default is not None:
			self._default = default

	@property
	def default(self):
		"""
		Default value.  AttributeError is raised if no default
		value is set.
		"""
		return self._default


class Element(object):
	"""
	Base class for all element types.  This class is inspired by the
	class of the same name in the Python standard library's xml.dom
	package.  One important distinction is that the standard DOM
	element is used to represent the structure of a document at a much
	finer level of detail than here.  For example, in the case of the
	standard DOM element, each XML attribute is its own element being a
	child node of its tag, while here they are simply stored as
	attributes of the tag element itself.

	Despite the differences, the documentation for the xml.dom package,
	particularly that of the Element class and it's parent, the Node
	class, is useful as supplementary material in understanding how to
	use this class.
	"""
	# XML tag names are case sensitive:  compare with ==, !=, etc.
	tagName = None
	validchildren = frozenset()

	@classmethod
	def validattributes(cls):
		return frozenset(name for name in dir(cls) if isinstance(getattr(cls, name), attributeproxy))

	def __init__(self, attrs = None):
		"""
		Construct an element.  The argument is a
		sax.xmlreader.AttributesImpl object (see the xml.sax
		documentation, but it's basically a dictionary-like thing)
		used to set the element attributes.
		"""
		self.parentNode = None
		if attrs is None:
			self.attributes = AttributesImpl({})
		elif set(attrs.keys()) <= self.validattributes():
			self.attributes = attrs
		else:
			raise ElementError("%s element: invalid attribute(s) %s" % (self.tagName, ", ".join("'%s'" % key for key in set(attrs.keys()) - self.validattributes())))
		self.childNodes = []
		self.pcdata = None

	def start_tag(self, indent):
		"""
		Generate the string for the element's start tag.
		"""
		return u"%s<%s%s>" % (indent, self.tagName, u"".join(u" %s=\"%s\"" % keyvalue for keyvalue in self.attributes.items()))

	def end_tag(self, indent):
		"""
		Generate the string for the element's end tag.
		"""
		return u"%s</%s>" % (indent, self.tagName)

	def appendChild(self, child):
		"""
		Add a child to this element.  The child's parentNode
		attribute is updated, too.
		"""
		self.childNodes.append(child)
		child.parentNode = self
		self._verifyChildren(len(self.childNodes) - 1)
		return child

	def insertBefore(self, newchild, refchild):
		"""
		Insert a new child node before an existing child. It must
		be the case that refchild is a child of this node; if not,
		ValueError is raised. newchild is returned.
		"""
		for i, childNode in enumerate(self.childNodes):
			if childNode is refchild:
				self.childNodes.insert(i, newchild)
				newchild.parentNode = self
				self._verifyChildren(i)
				return newchild
		raise ValueError(refchild)

	def removeChild(self, child):
		"""
		Remove a child from this element.  The child element is
		returned, and it's parentNode element is reset.  If the
		child will not be used any more, you should call its
		unlink() method to promote garbage collection.
		"""
		for i, childNode in enumerate(self.childNodes):
			if childNode is child:
				del self.childNodes[i]
				child.parentNode = None
				return child
		raise ValueError(child)

	def unlink(self):
		"""
		Break internal references within the document tree rooted
		on this element to promote garbage collection.
		"""
		self.parentNode = None
		for child in self.childNodes:
			child.unlink()
		del self.childNodes[:]

	def replaceChild(self, newchild, oldchild):
		"""
		Replace an existing node with a new node. It must be the
		case that oldchild is a child of this node; if not,
		ValueError is raised. newchild is returned.
		"""
		# .index() would use compare-by-value, we want
		# compare-by-id because we want to find the exact object,
		# not something equivalent to it.
		for i, childNode in enumerate(self.childNodes):
			if childNode is oldchild:
				self.childNodes[i].parentNode = None
				self.childNodes[i] = newchild
				newchild.parentNode = self
				self._verifyChildren(i)
				return newchild
		raise ValueError(oldchild)

	def getElements(self, filter):
		"""
		Return a list of elements below and including this element
		for which filter(element) returns True.
		"""
		l = reduce(lambda l, e: l + e.getElements(filter), self.childNodes, [])
		if filter(self):
			l.append(self)
		return l

	def getElementsByTagName(self, tagName):
		return self.getElements(lambda e: e.tagName == tagName)

	def getChildrenByAttributes(self, attrs):
		l = []
		for c in self.childNodes:
			try:
				if reduce(lambda t, kv: t and (c.getAttribute(kv[0]) == kv[1]), six.iteritems(attrs), True):
					l.append(c)
			except KeyError:
				pass
		return l

	def hasAttribute(self, attrname):
		return attrname in self.attributes

	def getAttribute(self, attrname):
		return self.attributes[attrname]

	def setAttribute(self, attrname, value):
		# cafeful:  this digs inside an AttributesImpl object and
		# modifies its internal data.  probably not a good idea,
		# but I don't know how else to edit an attribute because
		# the stupid things don't export a method to do it.
		self.attributes._attrs[attrname] = six.text_type(value)

	def removeAttribute(self, attrname):
		# cafeful:  this digs inside an AttributesImpl object and
		# modifies its internal data.  probably not a good idea,
		# but I don't know how else to edit an attribute because
		# the stupid things don't export a method to do it.
		try:
			del self.attributes._attrs[attrname]
		except KeyError:
			pass

	def appendData(self, content):
		"""
		Add characters to the element's pcdata.
		"""
		if self.pcdata is not None:
			self.pcdata += content
		else:
			self.pcdata = content

	def _verifyChildren(self, i):
		"""
		Method used internally by some elements to verify that
		their children are from the allowed set and in the correct
		order following modifications to their child list.  i is
		the index of the child that has just changed.
		"""
		pass

	def endElement(self):
		"""
		Method invoked by document parser when it encounters the
		end-of-element event.
		"""
		pass

	def write(self, fileobj = sys.stdout, indent = u""):
		"""
		Recursively write an element and it's children to a file.
		"""
		fileobj.write(self.start_tag(indent))
		fileobj.write(u"\n")
		for c in self.childNodes:
			if c.tagName not in self.validchildren:
				raise ElementError("invalid child %s for %s" % (c.tagName, self.tagName))
			c.write(fileobj, indent + Indent)
		if self.pcdata is not None:
			fileobj.write(xmlescape(self.pcdata))
			fileobj.write(u"\n")
		fileobj.write(self.end_tag(indent))
		fileobj.write(u"\n")


class EmptyElement(Element):
	"""
	Parent class for Elements that cannot contain text.
	"""
	def appendData(self, content):
		if not content.isspace():
			raise TypeError("%s does not hold text" % type(self))


def WalkChildren(elem):
	"""
	Walk the XML tree of children below elem, returning each in order.
	"""
	for child in elem.childNodes:
		yield child
		for elem in WalkChildren(child):
			yield elem


#
# =============================================================================
#
#                         Name Attribute Manipulation
#
# =============================================================================
#


class LLWNameAttr(six.text_type):
	"""
	Baseclass to hide pattern-matching of various element names.
	Subclasses must provide a .dec_pattern compiled regular expression
	defining a group "Name" that identifies the meaningful portion of
	the string, and a .enc_pattern that gives a format string to be
	used with "%" to reconstrct the full string.

	This is intended to be used to provide the enc and dec functions
	for an attributeproxy instance.

	Example:

	>>> import re
	>>> class Test(Element):
	...	class TestName(LLWNameAttr):
	...		dec_pattern = re.compile(r"(?P<Name>[a-z0-9_]+):test\Z")
	...		enc_pattern = u"%s:test"
	...
	...	Name = attributeproxy(u"Name", enc = TestName.enc, dec = TestName)
	...
	>>> x = Test()
	>>> x.Name = u"blah"
	>>> # internally, suffix has been appended
	>>> x.getAttribute("Name")
	u'blah:test'
	>>> # but attributeproxy reports original value
	>>> x.Name
	u'blah'
	"""
	def __new__(cls, name):
		try:
			name = cls.dec_pattern.search(name).group(u"Name")
		except AttributeError:
			pass
		return six.text_type.__new__(cls, name)

	@classmethod
	def enc(cls, name):
		return cls.enc_pattern % name


#
# =============================================================================
#
#                        LIGO Light Weight XML Elements
#
# =============================================================================
#


class LIGO_LW(EmptyElement):
	"""
	LIGO_LW element.
	"""
	tagName = u"LIGO_LW"
	validchildren = frozenset([u"LIGO_LW", u"Comment", u"Param", u"Table", u"Array", u"Stream", u"IGWDFrame", u"AdcData", u"AdcInterval", u"Time", u"Detector"])

	Name = attributeproxy(u"Name")
	Type = attributeproxy(u"Type")


class Comment(Element):
	"""
	Comment element.
	"""
	tagName = u"Comment"

	def write(self, fileobj = sys.stdout, indent = u""):
		fileobj.write(self.start_tag(indent))
		if self.pcdata is not None:
			fileobj.write(xmlescape(self.pcdata))
		fileobj.write(self.end_tag(u""))
		fileobj.write(u"\n")


class Param(Element):
	"""
	Param element.
	"""
	tagName = u"Param"
	validchildren = frozenset([u"Comment"])

	DataUnit = attributeproxy(u"DataUnit")
	Name = attributeproxy(u"Name")
	Scale = attributeproxy(u"Scale")
	Start = attributeproxy(u"Start")
	Type = attributeproxy(u"Type")
	Unit = attributeproxy(u"Unit")


class Table(EmptyElement):
	"""
	Table element.
	"""
	tagName = u"Table"
	validchildren = frozenset([u"Comment", u"Column", u"Stream"])

	Name = attributeproxy(u"Name")
	Type = attributeproxy(u"Type")

	def _verifyChildren(self, i):
		ncomment = 0
		ncolumn = 0
		nstream = 0
		for child in self.childNodes:
			if child.tagName == Comment.tagName:
				if ncomment:
					raise ElementError("only one Comment allowed in Table")
				if ncolumn or nstream:
					raise ElementError("Comment must come before Column(s) and Stream in Table")
				ncomment += 1
			elif child.tagName == Column.tagName:
				if nstream:
					raise ElementError("Column(s) must come before Stream in Table")
				ncolumn += 1
			else:
				if nstream:
					raise ElementError("only one Stream allowed in Table")
				nstream += 1


class Column(EmptyElement):
	"""
	Column element.
	"""
	tagName = u"Column"

	Name = attributeproxy(u"Name")
	Type = attributeproxy(u"Type")
	Unit = attributeproxy(u"Unit")

	def start_tag(self, indent):
		"""
		Generate the string for the element's start tag.
		"""
		return u"%s<%s%s/>" % (indent, self.tagName, u"".join(u" %s=\"%s\"" % keyvalue for keyvalue in self.attributes.items()))

	def end_tag(self, indent):
		"""
		Generate the string for the element's end tag.
		"""
		return u""

	def write(self, fileobj = sys.stdout, indent = u""):
		"""
		Recursively write an element and it's children to a file.
		"""
		fileobj.write(self.start_tag(indent))
		fileobj.write(u"\n")


class Array(EmptyElement):
	"""
	Array element.
	"""
	tagName = u"Array"
	validchildren = frozenset([u"Dim", u"Stream"])

	Name = attributeproxy(u"Name")
	Type = attributeproxy(u"Type")
	Unit = attributeproxy(u"Unit")

	def _verifyChildren(self, i):
		nstream = 0
		for child in self.childNodes:
			if child.tagName == Dim.tagName:
				if nstream:
					raise ElementError("Dim(s) must come before Stream in Array")
			else:
				if nstream:
					raise ElementError("only one Stream allowed in Array")
				nstream += 1


class Dim(Element):
	"""
	Dim element.
	"""
	tagName = u"Dim"

	Name = attributeproxy(u"Name")
	Scale = attributeproxy(u"Scale", enc = ligolwtypes.FormatFunc[u"real_8"], dec = ligolwtypes.ToPyType[u"real_8"])
	Start = attributeproxy(u"Start", enc = ligolwtypes.FormatFunc[u"real_8"], dec = ligolwtypes.ToPyType[u"real_8"])
	Unit = attributeproxy(u"Unit")

	@property
	def n(self):
		return ligolwtypes.ToPyType[u"int_8s"](self.pcdata) if self.pcdata is not None else None

	@n.setter
	def n(self, val):
		self.pcdata = ligolwtypes.FormatFunc[u"int_8s"](val) if val is not None else None

	@n.deleter
	def n(self):
		self.pcdata = None

	def write(self, fileobj = sys.stdout, indent = u""):
		fileobj.write(self.start_tag(indent))
		if self.pcdata is not None:
			fileobj.write(xmlescape(self.pcdata))
		fileobj.write(self.end_tag(u""))
		fileobj.write(u"\n")


class Stream(Element):
	"""
	Stream element.
	"""
	tagName = u"Stream"

	Content = attributeproxy(u"Content")
	Delimiter = attributeproxy(u"Delimiter", default = u",")
	Encoding = attributeproxy(u"Encoding")
	Name = attributeproxy(u"Name")
	Type = attributeproxy(u"Type", default = u"Local")

	def __init__(self, *args):
		super(Stream, self).__init__(*args)
		if self.Type not in (u"Remote", u"Local"):
			raise ElementError("invalid Type for Stream: '%s'" % self.Type)


class IGWDFrame(EmptyElement):
	"""
	IGWDFrame element.
	"""
	tagName = u"IGWDFrame"
	validchildren = frozenset([u"Comment", u"Param", u"Time", u"Detector", u"AdcData", u"LIGO_LW", u"Stream", u"Array", u"IGWDFrame"])

	Name = attributeproxy(u"Name")


class Detector(EmptyElement):
	"""
	Detector element.
	"""
	tagName = u"Detector"
	validchildren = frozenset([u"Comment", u"Param", u"LIGO_LW"])

	Name = attributeproxy(u"Name")


class AdcData(EmptyElement):
	"""
	AdcData element.
	"""
	tagName = u"AdcData"
	validchildren = frozenset([u"AdcData", u"Comment", u"Param", u"Time", u"LIGO_LW", u"Array"])

	Name = attributeproxy(u"Name")


class AdcInterval(EmptyElement):
	"""
	AdcInterval element.
	"""
	tagName = u"AdcInterval"
	validchildren = frozenset([u"AdcData", u"Comment", u"Time"])

	DeltaT = attributeproxy(u"DeltaT", enc = ligolwtypes.FormatFunc[u"real_8"], dec = ligolwtypes.ToPyType[u"real_8"])
	Name = attributeproxy(u"Name")
	StartTime = attributeproxy(u"StartTime")


class Time(Element):
	"""
	Time element.
	"""
	tagName = u"Time"

	Name = attributeproxy(u"Name")
	Type = attributeproxy(u"Type", default = u"ISO-8601")

	def __init__(self, *args):
		super(Time, self).__init__(*args)
		if self.Type not in ligolwtypes.TimeTypes:
			raise ElementError("invalid Type for Time: '%s'" % self.Type)

	def endElement(self):
		if self.Type == u"ISO-8601":
			import dateutil.parser
			self.pcdata = dateutil.parser.parse(self.pcdata)
		elif self.Type == u"GPS":
			from lal import LIGOTimeGPS
			# FIXME:  remove cast to string when lal swig
			# can cast from unicode
			self.pcdata = LIGOTimeGPS(str(self.pcdata))
		elif self.Type == u"Unix":
			self.pcdata = float(self.pcdata)
		else:
			# unsupported time type.  not impossible that
			# calling code has overridden TimeTypes set in
			# ligo.lw.types;  just accept it as a string
			pass

	def write(self, fileobj = sys.stdout, indent = u""):
		fileobj.write(self.start_tag(indent))
		if self.pcdata is not None:
			if self.Type == u"ISO-8601":
				fileobj.write(xmlescape(six.text_type(self.pcdata.isoformat())))
			elif self.Type == u"GPS":
				fileobj.write(xmlescape(six.text_type(self.pcdata)))
			elif self.Type == u"Unix":
				fileobj.write(xmlescape(u"%.16g" % self.pcdata))
			else:
				# unsupported time type.  not impossible.
				# assume correct thing to do is cast to
				# unicode and let calling code figure out
				# how to ensure that does the correct
				# thing.
				fileobj.write(xmlescape(six.text_type(self.pcdata)))
		fileobj.write(self.end_tag(u""))
		fileobj.write(u"\n")

	@classmethod
	def now(cls, Name = None):
		"""
		Instantiate a Time element initialized to the current UTC
		time in the default format (ISO-8601).  The Name attribute
		will be set to the value of the Name parameter if given.
		"""
		import datetime
		self = cls()
		if Name is not None:
			self.Name = Name
		self.pcdata = datetime.datetime.utcnow()
		return self

	@classmethod
	def from_gps(cls, gps, Name = None):
		"""
		Instantiate a Time element initialized to the value of the
		given GPS time.  The Name attribute will be set to the
		value of the Name parameter if given.

		Note:  the new Time element holds a reference to the GPS
		time, not a copy of it.  Subsequent modification of the GPS
		time object will be reflected in what gets written to disk.
		"""
		self = cls(AttributesImpl({u"Type": u"GPS"}))
		if Name is not None:
			self.Name = Name
		self.pcdata = gps
		return self


class Document(EmptyElement):
	"""
	Description of a LIGO LW file.
	"""
	tagName = u"Document"
	validchildren = frozenset([u"LIGO_LW"])

	def write(self, fileobj = sys.stdout, xsl_file = None):
		"""
		Write the document.
		"""
		fileobj.write(Header)
		fileobj.write(u"\n")
		if xsl_file is not None:
			fileobj.write(u'<?xml-stylesheet type="text/xsl" href="%s" ?>\n' % xsl_file)
		for c in self.childNodes:
			if c.tagName not in self.validchildren:
				raise ElementError("invalid child %s for %s" % (c.tagName, self.tagName))
			c.write(fileobj)


#
# =============================================================================
#
#                             SAX Content Handler
#
# =============================================================================
#


class LIGOLWContentHandler(sax.handler.ContentHandler, object):
	"""
	ContentHandler class for parsing LIGO Light Weight documents with a
	SAX2-compliant parser.

	Example:

	>>> # initialize empty Document tree into which parsed XML tree
	>>> # will be inserted
	>>> xmldoc = Document()
	>>> # create handler instance attached to Document object
	>>> handler = LIGOLWContentHandler(xmldoc)
	>>> # open file and parse
	>>> make_parser(handler).parse(open("demo.xml"))
	>>> # write XML (default to stdout)
	>>> xmldoc.write()

	NOTE:  this example is for illustration only.  Most users will wish
	to use the .load_*() functions in the ligo.lw.utils subpackage to
	load documents, and the .write_*() functions to write documents.
	Those functions provide additional features such as support for
	gzip'ed documents, MD5 hash computation, and Condor eviction
	trapping to avoid writing broken documents to disk.

	See also:  PartialLIGOLWContentHandler,
	FilteringLIGOLWContentHandler.
	"""

	def __init__(self, document, start_handlers = {}):
		"""
		Initialize the handler by pointing it to the Document object
		into which the parsed file will be loaded.
		"""
		self.current = self.document = document

		self._startElementHandlers = {
			(None, AdcData.tagName): self.startAdcData,
			(None, AdcInterval.tagName): self.startAdcInterval,
			(None, Array.tagName): self.startArray,
			(None, Column.tagName): self.startColumn,
			(None, Comment.tagName): self.startComment,
			(None, Detector.tagName): self.startDetector,
			(None, Dim.tagName): self.startDim,
			(None, IGWDFrame.tagName): self.startIGWDFrame,
			(None, LIGO_LW.tagName): self.startLIGO_LW,
			(None, Param.tagName): self.startParam,
			(None, Stream.tagName): self.startStream,
			(None, Table.tagName): self.startTable,
			(None, Time.tagName): self.startTime,
		}
		self._startElementHandlers.update(start_handlers)

	def startAdcData(self, parent, attrs):
		return AdcData(attrs)

	def startAdcInterval(self, parent, attrs):
		return AdcInterval(attrs)

	def startArray(self, parent, attrs):
		return Array(attrs)

	def startColumn(self, parent, attrs):
		return Column(attrs)

	def startComment(self, parent, attrs):
		return Comment(attrs)

	def startDetector(self, parent, attrs):
		return Detector(attrs)

	def startDim(self, parent, attrs):
		return Dim(attrs)

	def startIGWDFrame(self, parent, attrs):
		return IGWDFrame(attrs)

	def startLIGO_LW(self, parent, attrs):
		return LIGO_LW(attrs)

	def startParam(self, parent, attrs):
		return Param(attrs)

	def startStream(self, parent, attrs):
		return Stream(attrs)

	def startTable(self, parent, attrs):
		return Table(attrs)

	def startTime(self, parent, attrs):
		return Time(attrs)

	def startElementNS(self, uri_localname, qname, attrs):
		(uri, localname) = uri_localname
		try:
			start_handler = self._startElementHandlers[(uri, localname)]
		except KeyError:
			raise ElementError("unknown element %s for namespace %s" % (localname, uri or NameSpace))
		attrs = AttributesImpl(dict((attrs.getQNameByName(name), value) for name, value in attrs.items()))
		try:
			self.current = self.current.appendChild(start_handler(self.current, attrs))
		except Exception as e:
			raise type(e)("line %d: %s" % (self._locator.getLineNumber(), str(e)))

	def endElementNS(self, uri_localname, qname):
		(uri, localname) = uri_localname
		try:
			self.current.endElement()
		except Exception as e:
			raise type(e)("line %d: %s" % (self._locator.getLineNumber(), str(e)))
		self.current = self.current.parentNode

	def characters(self, content):
		try:
			self.current.appendData(xmlunescape(content))
		except Exception as e:
			raise type(e)("line %d: %s" % (self._locator.getLineNumber(), str(e)))


class PartialLIGOLWContentHandler(LIGOLWContentHandler):
	"""
	LIGO LW content handler object that loads only those parts of the
	document matching some criteria.  Useful, for example, when one
	wishes to read only a single table from a file.

	Example:

	>>> from ligo.lw import utils as ligolw_utils
	>>> def contenthandler(document):
	...	return PartialLIGOLWContentHandler(document, lambda name, attrs: name == Table.tagName)
	...
	>>> xmldoc = ligolw_utils.load_filename("demo.xml", contenthandler = contenthandler)

	This parses "demo.xml" and returns an XML tree containing only the
	Table elements and their children.
	"""
	def __init__(self, document, element_filter):
		"""
		Only those elements for which element_filter(name, attrs)
		evaluates to True, and the children of those elements, will
		be loaded.
		"""
		super(PartialLIGOLWContentHandler, self).__init__(document)
		self.element_filter = element_filter
		self.depth = 0

	def startElementNS(self, uri_localname, qname, attrs):
		(uri, localname) = uri_localname
		filter_attrs = AttributesImpl(dict((attrs.getQNameByName(name), value) for name, value in attrs.items()))
		if self.depth > 0 or self.element_filter(localname, filter_attrs):
			super(PartialLIGOLWContentHandler, self).startElementNS((uri, localname), qname, attrs)
			self.depth += 1

	def endElementNS(self, *args):
		if self.depth > 0:
			self.depth -= 1
			super(PartialLIGOLWContentHandler, self).endElementNS(*args)

	def characters(self, content):
		if self.depth > 0:
			super(PartialLIGOLWContentHandler, self).characters(content)


class FilteringLIGOLWContentHandler(LIGOLWContentHandler):
	"""
	LIGO LW content handler that loads everything but those parts of a
	document that match some criteria.  Useful, for example, when one
	wishes to read everything except a single table from a file.

	Example:

	>>> from ligo.lw import utils as ligolw_utils
	>>> def contenthandler(document):
	...	return FilteringLIGOLWContentHandler(document, lambda name, attrs: name != Table.tagName)
	...
	>>> xmldoc = ligolw_utils.load_filename("demo.xml", contenthandler = contenthandler)

	This parses "demo.xml" and returns an XML tree with all the Table
	elements and their children removed.
	"""
	def __init__(self, document, element_filter):
		"""
		Those elements for which element_filter(name, attrs)
		evaluates to False, and the children of those elements,
		will not be loaded.
		"""
		super(FilteringLIGOLWContentHandler, self).__init__(document)
		self.element_filter = element_filter
		self.depth = 0

	def startElementNS(self, uri_localname, qname, attrs):
		(uri, localname) = uri_localname
		filter_attrs = AttributesImpl(dict((attrs.getQNameByName(name), value) for name, value in attrs.items()))
		if self.depth == 0 and self.element_filter(localname, filter_attrs):
			super(FilteringLIGOLWContentHandler, self).startElementNS((uri, localname), qname, attrs)
		else:
			self.depth += 1

	def endElementNS(self, *args):
		if self.depth == 0:
			super(FilteringLIGOLWContentHandler, self).endElementNS(*args)
		else:
			self.depth -= 1

	def characters(self, content):
		if self.depth == 0:
			super(FilteringLIGOLWContentHandler, self).characters(content)


#
# =============================================================================
#
#                            Convenience Functions
#
# =============================================================================
#


def make_parser(handler):
	"""
	Convenience function to construct a document parser with namespaces
	enabled and validation disabled.  Document validation is a nice
	feature, but enabling validation can require the LIGO LW DTD to be
	downloaded from the LDAS document server if the DTD is not included
	inline in the XML.  This requires a working connection to the
	internet and the server to be up.
	"""
	parser = sax.make_parser()
	parser.setContentHandler(handler)
	parser.setFeature(sax.handler.feature_namespaces, True)
	parser.setFeature(sax.handler.feature_validation, False)
	parser.setFeature(sax.handler.feature_external_ges, False)
	return parser
