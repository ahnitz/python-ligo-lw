/*
 * Copyright (C) 2006-2009,2016,2017  Kipp C. Cannon
 *
 * This program is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by the
 * Free Software Foundation; either version 2 of the License, or (at your
 * option) any later version.
 *
 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with this program; if not, write to the Free Software Foundation, Inc.,
 * 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
 */


/*
 * ============================================================================
 *
 *                     ligo.lw.tokenizer Extension Module
 *
 * ============================================================================
 */


#include <Python.h>
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>
#include <tokenizer.h>


/*
 * ============================================================================
 *
 *                              Helper Functions
 *
 * ============================================================================
 */


/*
 * Convert a sequence of unicode and/or strings to a tuple of unicodes.
 * Creates a reference to a new object, does not decref its argument.
 */


PyObject *llwtokenizer_build_attributes(PyObject *sequence)
{
	PyObject *result;
	int i;

	/* guaranteed to produce a new object */
	sequence = PySequence_List(sequence);
	if(!sequence)
		return NULL;

	for(i = 0; i < PyList_GET_SIZE(sequence); i++) {
		PyObject *item = PyList_GET_ITEM(sequence, i);
		if(!item) {
			Py_DECREF(sequence);
			return NULL;
		}
		if(!PyUnicode_Check(item)) {
			PyObject *str = PyUnicode_FromObject(item);
			if(!str) {
				Py_DECREF(sequence);
				return NULL;
			}
			Py_DECREF(item);
			PyList_SET_ITEM(sequence, i, str);
		}
	}

	result = PySequence_Tuple(sequence);
	Py_DECREF(sequence);

	return result;
}


/*
 * Convert a sequence of functions to a tuple of functions.  Creates a
 * reference to a new object, does not decref its argument.
 */


PyObject *llwtokenizer_build_formats(PyObject *sequence)
{
	return PySequence_Tuple(sequence);
}


/*
 * ============================================================================
 *
 *                            Module Registration
 *
 * ============================================================================
 */


#define MODULE_DOC \
"This module provides a tokenizer for LIGO Light Weight XML Stream and Array\n" \
"elements, as well as other utilities to assist in packing parsed tokens into\n" \
"various data storage units."


#if PY_MAJOR_VERSION < 3
PyMODINIT_FUNC inittokenizer(void); /* Silence -Wmissing-prototypes */
PyMODINIT_FUNC inittokenizer(void)
#else
PyMODINIT_FUNC PyInit_tokenizer(void); /* Silence -Wmissing-prototypes */
PyMODINIT_FUNC PyInit_tokenizer(void)
#endif
{
	/*
	 * Create the module.
	 */

#if PY_MAJOR_VERSION < 3
	PyObject *module = Py_InitModule3(MODULE_NAME, NULL, MODULE_DOC);
#else
	static PyModuleDef moduledef = {
		PyModuleDef_HEAD_INIT,
		MODULE_NAME, MODULE_DOC, -1, NULL
	};
	PyObject *module = PyModule_Create(&moduledef);
#endif
	if (!module)
		goto done;

	/*
	 * Initialize the classes
	 */

	if(PyType_Ready(&ligolw_Tokenizer_Type) < 0)
		goto done;
	if(PyType_Ready(&ligolw_RowBuilder_Type) < 0)
		goto done;
	if(PyType_Ready(&ligolw_RowDumper_Type) < 0)
		goto done;

	/*
	 * Add the Tokenizer class.
	 */

	Py_INCREF(&ligolw_Tokenizer_Type);
	PyModule_AddObject(module, "Tokenizer", (PyObject *) &ligolw_Tokenizer_Type);

	/*
	 * Add the RowBuilder class.
	 */

	Py_INCREF(&ligolw_RowBuilder_Type);
	PyModule_AddObject(module, "RowBuilder", (PyObject *) &ligolw_RowBuilder_Type);

	/*
	 * Add the RowDumper class.
	 */

	Py_INCREF(&ligolw_RowDumper_Type);
	PyModule_AddObject(module, "RowDumper", (PyObject *) &ligolw_RowDumper_Type);

	/*
	 * Done.
	 */

done:
#if PY_MAJOR_VERSION < 3
	return;
#else
	return module;
#endif
}
