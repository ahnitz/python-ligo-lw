from distutils.core import setup, Extension


setup(
	name = "python-ligo-lw",
	version = "1.0.1",
	author = "Kipp Cannon",
	author_email = "kipp.cannon@ligo.org",
	description = "Python LIGO Light-Weight XML I/O Library",
	url = "https://git.ligo.org/kipp.cannon/python-ligo-lw",
	license = "GPL",
	namespace_packages = [
		"ligo",
	],
	packages = [
		"ligo.lw",
		"ligo.lw.utils"
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
	]
)
