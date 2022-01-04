/*
 * Copyright (C) 2006-2009,2016,2017,2020,2021  Kipp C. Cannon
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


static int type_ready_and_add(PyObject *module, const char *name, PyTypeObject *type)
{
	if(!type || PyType_Ready(type) < 0)
		return -1;

	Py_INCREF(type);
	if(PyModule_AddObject(module, name, (PyObject *) type) < 0) {
		Py_DECREF(type);
		return -1;
	}

	return 0;
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


PyMODINIT_FUNC PyInit_tokenizer(void); /* Silence -Wmissing-prototypes */
PyMODINIT_FUNC PyInit_tokenizer(void)
{
	/*
	 * Create the module.
	 */

	static PyModuleDef moduledef = {
		PyModuleDef_HEAD_INIT,
		MODULE_NAME, MODULE_DOC, -1, NULL
	};
	PyObject *module = PyModule_Create(&moduledef);
	if(!module)
		goto error;

	/*
	 * Initialize the classes and add to module
	 */

	if(type_ready_and_add(module, "Tokenizer", &ligolw_Tokenizer_Type) < 0)
		goto error;
	if(type_ready_and_add(module, "RowBuilder", &ligolw_RowBuilder_Type) < 0)
		goto error;
	if(type_ready_and_add(module, "RowDumper", &ligolw_RowDumper_Type) < 0)
		goto error;

	/*
	 * Done.
	 */

	return module;

error:
	Py_XDECREF(module);
	return NULL;
}
