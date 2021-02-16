from distutils.core import setup, Extension


__version__ = "1.7.1"
__date__ = "2021-02-16"


def macroreplace(filenames, substs):
	"""
	Autoconf-style macro replacement
	"""
	for filename in filenames:
		if not filename.endswith(".in"):
			raise ValueError("\"%s\" must end in \".in\"" % filename)
	for pattern in substs:
		if not pattern.startswith("@") or not pattern.endswith("@"):
			raise ValueError("bad pattern \"%s\"" % pattern)
	for filename in filenames:
		with open(filename[:-3], "w") as outfile:
			for line in open(filename, "r"):
				for pattern, value in substs.items():
					line = line.replace(pattern, value)
				outfile.write(line)


macroreplace([
	"ligo/lw/__init__.py.in",
	"python-ligo-lw.spec.in",
], {
	"@VERSION@": __version__,
	"@DATE@": __date__,
})


setup(
	name = "python-ligo-lw",
	version = __version__,
	author = "Kipp Cannon",
	author_email = "kipp.cannon@ligo.org",
	description = "Python LIGO Light-Weight XML I/O Library",
	long_description = "The LIGO Light-Weight XML format is used extensively by compact object detection pipeline and associated tool sets.  This package provides a Python I/O library for reading, writing, and interacting with documents in this format.",
	url = "https://git.ligo.org/kipp.cannon/python-ligo-lw",
	license = "GPL",
	namespace_packages = [
		"ligo",
	],
	packages = [
		"ligo",
		"ligo.lw",
		"ligo.lw.utils",
	],
	ext_modules = [
		Extension(
			"ligo.lw._ilwd",
			[
				"ligo/lw/ilwd.c",
			],
			include_dirs = ["ligo/lw"]
		),
		Extension(
			"ligo.lw.tokenizer",
			[
				"ligo/lw/tokenizer.c",
				"ligo/lw/tokenizer.Tokenizer.c",
				"ligo/lw/tokenizer.RowBuilder.c",
				"ligo/lw/tokenizer.RowDumper.c",
			],
			include_dirs = ["ligo/lw"]
		),
	],
	scripts = [
		"bin/ligolw_add",
		"bin/ligolw_cut",
		"bin/ligolw_no_ilwdchar",
		"bin/ligolw_print",
		"bin/ligolw_segments",
		"bin/ligolw_sqlite",
	],
	classifiers = [
		"Development Status :: 6 - Mature",
		"Intended Audience :: Science/Research",
		"License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)",
		"Natural Language :: English",
		"Operating System :: POSIX",
		"Programming Language :: Python :: 2.7",
		"Programming Language :: Python :: 3",
		"Topic :: Scientific/Engineering :: Astronomy",
		"Topic :: Scientific/Engineering :: Physics",
		"Topic :: Software Development :: Libraries",
		"Topic :: Text Processing :: Markup :: XML",
	],
	install_requires = [
		"ligo-segments",
		"lscsoft-glue",
		"numpy",
		"python-dateutil",
		"pyyaml",
		"six",
		"tqdm"
	]
)
