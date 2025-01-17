/*
 * Copyright (C) 2006-2009,2011,2014-2017  Kipp C. Cannon
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
 *                         tokenizer.Tokenizer Class
 *
 * ============================================================================
 */


/* Silence warning in Python 3.8. See https://bugs.python.org/issue36381 */
#define PY_SSIZE_T_CLEAN

#include <Python.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <tokenizer.h>
#include <wchar.h>
#include <wctype.h>


/*
 * ============================================================================
 *
 *                               Tokenizer Type
 *
 * ============================================================================
 */


/*
 * The escape character.
 */


#define ESCAPE_CHARACTER L'\\'


/*
 * Globally-defined, statically-allocated, default list of quote
 * characters.
 */


static const wchar_t default_quote_characters[] = {L'\'', L'\"', 0};


/*
 * Structure
 */


typedef struct {
	PyObject_HEAD
	/* list of the types to which parsed tokens will be converted */
	PyObject **types;
	/* end of the types list */
	PyObject **types_length;
	/* the type to which the next parsed token will be converted */
	PyObject **type;
	/* delimiter character to be used in parsing */
	wchar_t delimiter;
	/* size of internal buffer, minus null terminator */
	Py_ssize_t allocation;
	/* internal buffer */
	wchar_t *data;
	/* end of internal buffer's contents (null terminator) */
	wchar_t *length;
	/* current offset in buffer */
	wchar_t *pos;
} ligolw_Tokenizer;


/*
 * Append the contents of a unicode object to a tokenizer's internal
 * buffer, increasing the size of the buffer if needed.
 */


static int add_to_data(ligolw_Tokenizer *tokenizer, PyObject *unicode)
{
	Py_ssize_t n = PyUnicode_GET_LENGTH(unicode);

	if(n) {
		if(tokenizer->length - tokenizer->data + n > tokenizer->allocation) {
			/*
			 * convert pointers to integer offsets
			 */

			ptrdiff_t pos = tokenizer->pos - tokenizer->data;
			ptrdiff_t length = tokenizer->length - tokenizer->data;

			/*
			 * increase buffer size, adding 1 to leave room for
			 * the null terminator
			 */

			wchar_t *old_data = tokenizer->data;

			tokenizer->data = realloc(tokenizer->data, (tokenizer->allocation + n + 1) * sizeof(*tokenizer->data));
			if(!tokenizer->data) {
				/*
				 * memory failure, restore pointer and exit
				 */

				tokenizer->data = old_data;
				return -1;
			}
			tokenizer->allocation += n;

			/*
			 * convert integer offsets back to pointers
			 */

			tokenizer->pos = &tokenizer->data[pos];
			tokenizer->length = &tokenizer->data[length];
		}

		/*
		 * copy data from unicode into buffer, appending null
		 * terminator
		 */

		PyUnicode_AsWideChar(unicode, tokenizer->length, n);
		tokenizer->length += n;
		*tokenizer->length = 0;
	}

	/*
	 * success
	 */

	return 0;
}


/*
 * Shift the contents of the tokenizer's buffer so that the data starting
 * at pos is moved to the start of the buffer.  When moving data, add 1 to
 * the length to also move the null terminator.  Only at most 1 token can
 * remain in the buffer, so the volume of data copied will usually not be
 * more than a few bytes.  It's not worth trying to avoid this by using a
 * circular buffer.  That would complicate token parsing elsewhere since
 * each token's bytes could no longer be trusted to be contiguous in
 * memory.
 */


static void advance_to_pos(ligolw_Tokenizer *tokenizer)
{
	if(tokenizer->pos != tokenizer->data) {
		tokenizer->length -= tokenizer->pos - tokenizer->data;
		memmove(tokenizer->data, tokenizer->pos, (tokenizer->length - tokenizer->data + 1) * sizeof(*tokenizer->data));
		tokenizer->pos = tokenizer->data;
	}
}


/*
 * Free the tokenizer's types list.
 */


static void unref_types(ligolw_Tokenizer *tokenizer)
{
	for(tokenizer->type = tokenizer->types; tokenizer->type < tokenizer->types_length; tokenizer->type++)
		Py_DECREF(*tokenizer->type);

	free(tokenizer->types);
	tokenizer->types = NULL;
	tokenizer->types_length = NULL;
	tokenizer->type = NULL;
}


/*
 * Construct a parser error message.
 */


static void parse_error(PyObject *exception, const wchar_t *buffer, const ptrdiff_t buffer_length, const wchar_t *pos, const char *msg)
{
	PyObject *buffer_str;
	PyObject *pos_str;

	buffer_str = PyUnicode_FromWideChar(buffer, buffer_length);
	pos_str = PyUnicode_FromWideChar(pos, 1);

	if(buffer_str && pos_str)
		PyErr_Format(exception, "parse error in '%U' near '%U' at position %zd: %s", buffer_str, pos_str, (Py_ssize_t) (pos - buffer + 1), msg);
	else
		PyErr_Format(exception, "parse error (details not available): %s", msg);

	Py_XDECREF(buffer_str);
	Py_XDECREF(pos_str);
}


/*
 * Unescape a string.
 */


static int unescape(wchar_t *start, wchar_t **end, const wchar_t *escapable_characters)
{
	wchar_t *i, *j;

	/*
	 * Search for first escape character.  If not found, we have
	 * nothing to do.  This is a fast-path for the common case of
	 * strings with no special characters.
	 */

	i = wcschr(start, ESCAPE_CHARACTER);
	if(!i)
		return 0;

	/*
	 * Process the rest of the string, unescaping special characters by
	 * shifting them to the left in the buffer.
	 */

	for(j = i; *i; *(i++) = *(j++)) {
		/*
		 * Is this character the escape character?
		 */

		if(*j != ESCAPE_CHARACTER)
			continue;

		/*
		 * Check for an unrecognized escape sequence, or an escape
		 * sequence starting in the last character position.
		 */

		if(!*(++j)) {
			parse_error(PyExc_RuntimeError, start, *end - start - 1, *end - 1, "internal error: incomplete escape sequence at end of string");
			return -1;
		} else if(!wcschr(escapable_characters, *j)) {
			parse_error(PyExc_ValueError, start, *end - start - 1, j - 1, "unrecognized escape sequence");
			return -1;
		}

		/*
		 * Update the end pointer
		 */

		(*end)--;
	}

	assert(i == *end);

	return 0;
}


/*
 * Identify the next token to extract from the tokenizer's internal buffer.
 * On success, start will be left pointing to the address of the start of
 * the string, and end will be pointing to the first character after the
 * string, which will be set to 0 (the token will be null-terminated).  If
 * an empty token is encountered (only whitespace between two delimiters)
 * then start and end are both set to NULL so that calling code can tell
 * the difference between a zero-length token and an absent token.  If a
 * non-empty token is found, it will be NULL terminated.  The return value
 * is the Python type to which the text should be converted, or NULL on
 * error.  On error, the values of start and end are undefined.  Raises
 * StopIteration if the end of the tokenizer's internal buffer is reached,
 * or ValueError if a parse error occurs.
 *
 * If an error occurs parsing must stop.  An error can result in the
 * tokenizer context being left unmodified, causing subsequent calls to
 * this function to repeatedly parse the same invalid token, leading to the
 * application getting stuck in an infinite loop.
 */


static PyObject *next_token(ligolw_Tokenizer *tokenizer, wchar_t **start, wchar_t **end)
{
	wchar_t *pos = tokenizer->pos;
	wchar_t *bailout = tokenizer->length;
	PyObject *type = *tokenizer->type;
	wchar_t quote_character;

	/*
	 * The following code matches the pattern:
	 *
	 * any amount of white-space + " + non-quote characters + " + any
	 * amount of white-space + delimiter
	 *
	 * or
	 *
	 * any amount of white-space + non-white-space, non-delimiter
	 * characters + any amount of white-space + delimiter
	 *
	 * The middle bit is returned as the token.  '"' and '\' characters
	 * can be escaped by preceding them with a '\' character.
	 */

	/*
	 * start == a white-space to non-white-space transition outside of
	 * a quote, or a non-quoted to quoted transition.
	 *
	 * end == a non-white-space to white-space transition outside of a
	 * quote, or a delimiter outside of a quote, or a quoted to
	 * non-quoted transition.
	 */

	if(pos >= bailout)
		goto stop_iteration;
	while(iswspace(*pos))
		if(++pos >= bailout)
			goto stop_iteration;
	if(wcschr(default_quote_characters, *pos)) {
		/*
		 * Found a quoted token.
		 */

		int escaped = 0;

		quote_character = *pos;

		*start = ++pos;
		if(pos >= bailout)
			goto stop_iteration;
		while((*pos != quote_character) || escaped) {
			escaped = (*pos == ESCAPE_CHARACTER) && !escaped;
			if(++pos >= bailout)
				goto stop_iteration;
		}
		*end = pos;
		if(++pos >= bailout)
			goto stop_iteration;
	} else {
		/*
		 * Found an unquoted token.
		 */

		quote_character = 0;

		*start = pos;
		while(!iswspace(*pos) && (*pos != tokenizer->delimiter))
			if(++pos >= bailout)
				goto stop_iteration;
		*end = pos;
		if(*start == *end)
			/*
			 * Found nothing but unquoted whitespace between
			 * delimiters --> an empty token (not the same as a
			 * zero-length token).
			 */

			*start = *end = NULL;
	}
	while(*pos != tokenizer->delimiter) {
		if(!iswspace(*pos)) {
			parse_error(PyExc_ValueError, *start, tokenizer->length - *start - 1, pos, "expected whitespace or delimiter");
			return NULL;
		}
		if(++pos >= bailout)
			goto stop_iteration;
	}

	/*
	 * After this, tokenizer->pos points to the first character after
	 * the delimiter that terminated this current token.
	 */

	tokenizer->pos = ++pos;

	/*
	 * Select the next type
	 */

	if(++tokenizer->type >= tokenizer->types_length)
		tokenizer->type = tokenizer->types;

	/*
	 * NULL terminate the token, and if it was quoted unescape special
	 * characters.  The unescape() function modifies the token in
	 * place, so we call it after advancing tokenizer->pos and
	 * tokenizer->type so that if a failure occurs we don't leave the
	 * tokenizer pointed at a garbled string.
	 */

	if(*end)
		**end = 0;
	if(quote_character) {
		wchar_t escapable_characters[] = {quote_character, ESCAPE_CHARACTER, 0};
		if(unescape(*start, end, escapable_characters))
			return NULL;
	}

	/*
	 * Done.  *start points to the first character of the token, *end
	 * points to the first character following the token (or both are
	 * NULL if there was nothing but unquoted whitespace),
	 * tokenizer->pos and tokenizer->type have been advanced in
	 * readiness for the next token, and the return value is the python
	 * type to which the current token is to be converted.
	 */

	return type;

	/*
	 * Errors
	 */

stop_iteration:
	advance_to_pos(tokenizer);
	PyErr_SetNone(PyExc_StopIteration);
	return NULL;
}


/*
 * append() method
 */


static PyObject *append(PyObject *self, PyObject *data)
{
	if(!PyUnicode_Check(data)) {
		PyErr_SetObject(PyExc_TypeError, data);
		return NULL;
	}

	/* FIXME:  remove when we require Python >= 3.12 */
#ifdef PyUnicode_READY
	PyUnicode_READY(data);
#endif
	if(add_to_data((ligolw_Tokenizer *) self, data) < 0)
		return PyErr_NoMemory();

	Py_INCREF(self);
	return self;
}


/*
 * __del__() method
 */


static void __del__(PyObject *self)
{
	ligolw_Tokenizer *tokenizer = (ligolw_Tokenizer *) self;

	unref_types(tokenizer);
	free(tokenizer->data);
	tokenizer->data = NULL;
	tokenizer->allocation = 0;
	tokenizer->length = NULL;
	tokenizer->pos = NULL;

	self->ob_type->tp_free(self);
}


/*
 * __init__() method
 */


static int __init__(PyObject *self, PyObject *args, PyObject *kwds)
{
	ligolw_Tokenizer *tokenizer = (ligolw_Tokenizer *) self;
	PyObject *arg;

	if(!PyArg_ParseTuple(args, "U", &arg))
		return -1;

	/* FIXME:  remove when we require Python >= 3.12 */
#ifdef PyUnicode_READY
	PyUnicode_READY(arg);
#endif

	if(PyUnicode_GET_LENGTH(arg) != 1) {
		PyErr_SetString(PyExc_ValueError, "len(delimiter) != 1");
		return -1;
	}

	PyUnicode_AsWideChar(arg, &tokenizer->delimiter, 1);
	tokenizer->types = malloc(1 * sizeof(*tokenizer->types));
	tokenizer->types_length = &tokenizer->types[1];
	tokenizer->types[0] = (PyObject *) &PyUnicode_Type;
	Py_INCREF(tokenizer->types[0]);
	tokenizer->type = tokenizer->types;
	tokenizer->allocation = 0;
	tokenizer->data = NULL;
	tokenizer->length = tokenizer->data;
	tokenizer->pos = tokenizer->data;

	return 0;
}


/*
 * __iter__() method
 */


static PyObject *__iter__(PyObject *self)
{
	Py_INCREF(self);
	return self;
}


/*
 * next() method
 */


static PyObject *next(PyObject *self)
{
	ligolw_Tokenizer *tokenizer = (ligolw_Tokenizer *) self;
	PyObject *type;
	PyObject *token;
	wchar_t *start, *end;

	/*
	 * Identify the start and end of the next token.
	 */

	do {
		type = next_token(tokenizer, &start, &end);
		if(!type)
			return NULL;
	} while(type == Py_None);

	/*
	 * Extract token as desired type.
	 */

	if(start == NULL) {
		/*
		 * unquoted zero-length string == None
		 */

		Py_INCREF(Py_None);
		token = Py_None;
	} else if(type == (PyObject *) &PyFloat_Type) {
		wchar_t *conversion_end;
		token = PyFloat_FromDouble(wcstod(start, &conversion_end));
		if(conversion_end == start || *conversion_end != 0) {
			/*
			 * wcstod() couldn't convert the token, emulate
			 * float()'s error message
			 */

			Py_XDECREF(token);
			token = PyUnicode_FromWideChar(start, -1);
			PyErr_Format(PyExc_ValueError, "invalid literal for float(): '%U'", token);
			Py_DECREF(token);
			token = NULL;
		}
	} else if(type == (PyObject *) &PyUnicode_Type) {
		token = PyUnicode_FromWideChar(start, end - start);
	} else if(type == (PyObject *) &PyLong_Type) {
		wchar_t *conversion_end;
		/* FIXME:  although Python supports arbitrary precision
		 * integers, this can only handle numbers that fit into a C
		 * long long.  in practice, since we invariably
		 * interoperate with C codes, that should be sufficient,
		 * but it's a limitation of the library and should probably
		 * be fixed */
		token = PyLong_FromLongLong(wcstoll(start, &conversion_end, 0));
		if(conversion_end == start || *conversion_end != 0) {
			/*
			 * wcstoll() couldn't convert the token, emulate
			 * long()'s error message
			 */

			Py_XDECREF(token);
			token = PyUnicode_FromWideChar(start, -1);
			PyErr_Format(PyExc_ValueError, "invalid literal for long(): '%U'", token);
			Py_DECREF(token);
			token = NULL;
		}
	} else {
		token = PyObject_CallFunction(type, "u#", start, end - start);
	}

	/*
	 * Done.
	 */

	return token;
}


/*
 * set_types() method
 */


static PyObject *set_types(PyObject *self, PyObject *sequence)
{
	ligolw_Tokenizer *tokenizer = (ligolw_Tokenizer *) self;
	Py_ssize_t length, i;

	/*
	 * Simplify the sequence access.
	 */

	sequence = PySequence_Tuple(sequence);
	if(!sequence)
		return NULL;
	length = PyTuple_GET_SIZE(sequence);

	/*
	 * Free the current internal type list.
	 */

	unref_types(tokenizer);

	/*
	 * Allocate a new internal type list.
	 */

	tokenizer->types = malloc(length * sizeof(*tokenizer->types));
	if(!tokenizer->types) {
		Py_DECREF(sequence);
		return PyErr_NoMemory();
	}
	tokenizer->type = tokenizer->types;
	tokenizer->types_length = &tokenizer->types[length];

	/*
	 * Copy the input sequence's contents into the internal type list.
	 */

	for(i = 0; i < length; i++) {
		tokenizer->types[i] = PyTuple_GET_ITEM(sequence, i);
		Py_INCREF(tokenizer->types[i]);
	}

	/*
	 * Done.
	 */

	Py_DECREF(sequence);
	Py_INCREF(Py_None);
	return Py_None;
}


/*
 * Attribute access.
 */


static PyObject *attribute_get_data(PyObject *obj, void *data)
{
	ligolw_Tokenizer *tokenizer = (ligolw_Tokenizer *) obj;

	return PyUnicode_FromWideChar(tokenizer->pos, tokenizer->length - tokenizer->pos);
}


/*
 * Type information
 */


static struct PyMethodDef methods[] = {
	{"append", append, METH_O, "Append a unicode string object to the tokenizer's internal buffer."},
	{"set_types", set_types, METH_O, "Set the types to be used cyclically for token parsing.  This function accepts an iterable of callables.  Each callable will be passed the token to be converted as a unicode string.  Special fast-paths are included to handle the Python builtin types float, int, long, and str.  The default is to return all tokens as unicode string objects."},
	{NULL,}
};


static struct PyGetSetDef getset[] = {
	{"data", attribute_get_data, NULL, "The current contents of the internal buffer.", NULL},
	{NULL,}
};


PyTypeObject ligolw_Tokenizer_Type = {
	PyObject_HEAD_INIT((long int) NULL)
	.tp_basicsize = sizeof(ligolw_Tokenizer),
	.tp_dealloc = __del__,
	.tp_doc =
"A tokenizer for LIGO Light Weight XML Stream and Array elements.  Converts\n" \
"(usually comma-) delimited text streams into sequences of Python objects.  An\n" \
"instance is created by calling the class with the delimiter character as the\n" \
"single argument.  Text is appended to the internal buffer by passing it to the\n" \
".append() method.  Tokens are extracted by iterating over the instance.  The\n" \
"Tokenizer is able to directly extract tokens as various Python types.  The\n" \
".set_types() method is passed a sequence of the types to which tokens are to be\n" \
"converted.  The types will be used in order, cyclically.  For example, passing\n" \
"[int] to set_types() causes all tokens to be converted to integers, while\n" \
"[str, int] causes the first token to be returned as a string, the second as an\n" \
"integer, then the third as a string again, and so on.  The default is to\n" \
"extract all tokens as strings.  If a token type is set to None then the\n" \
"corresponding tokens are skipped.  For example, invoking .set_types() with\n" \
"[int, None] causes the first token to be converted to an integer, the second\n" \
"to be skipped the third to be converted to an integer, and so on.  This can\n" \
"be used to improve parsing performance when only a subset of the input stream\n" \
"is required.\n" \
"\n" \
"Example:\n" \
"\n" \
">>> from ligo.lw import tokenizer\n" \
">>> t = tokenizer.Tokenizer(u\",\")\n" \
">>> t.set_types([str, int])\n" \
">>> list(t.append(\"a,10,b,2\"))\n" \
"['a', 10, 'b']\n" \
">>> list(t.append(\"0,\"))\n" \
"[20]\n" \
"\n" \
"Notes.  The last token will not be extracted until a delimiter character is\n" \
"seen to terminate it.  Tokens can be quoted with '\"' characters, which will\n" \
"be removed before conversion to the target type.  An empty token (two\n" \
"delimiters with only whitespace between them) is returned as None regardless\n" \
"of the requested type.  To prevent a zero-length string token from being\n" \
"interpreted as None, place it in quotes.",
	.tp_flags = Py_TPFLAGS_DEFAULT,
	.tp_init = __init__,
	.tp_iter = __iter__,
	.tp_iternext = next,
	.tp_getset = getset,
	.tp_methods = methods,
	.tp_name = MODULE_NAME ".Tokenizer",
	.tp_new = PyType_GenericNew,
};
