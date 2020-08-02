PYTHON ?= python3

check : \
	ligolw_print_test \
	ligolw_sqlite_test \
	ligo_lw_test_01 \
	ligolw_test03a \
	ligolw_test03b \
	ligolw_test03c \
	ligolw_test04 \
	ligolw_test05 \
	test_array \
	test_ilwd \
	test_ligolw \
	test_lsctables \
	test_param \
	test_table \
	test_tokenizer \
	test_utils \
	test_utils_process \
	test_utils_segments
	@echo "All Tests Passed"

define printpassfail
{ echo "Pass" ; true ; } || { echo "Fail" ; false ; }
endef

SERVEFILESPORT := 16543

define servefilestart
{ $(PYTHON) -c "import http.server ; http.server.HTTPServer(('127.0.0.1', $(SERVEFILESPORT)), http.server.SimpleHTTPRequestHandler).handle_request()" & sleep 1 ; }
endef
define servefilestop
wait
endef

ligolw_test03a :
	@echo "=== start $@ ===>"
	# test reading compressed and non-compressed files from stdin
	{ cat inspiral_event_id_test_in1.xml.gz | ligolw_print >/dev/null ; } && $(printpassfail)
	{ cat inspiral_event_id_test_in2.xml | ligolw_print >/dev/null ; } && $(printpassfail)
	@echo "<=== end $@ ==="

ligolw_test03b :
	@echo "=== start $@ ===>"
	# test reading compressed and non-compressed files
	ligolw_print inspiral_event_id_test_in1.xml.gz >/dev/null && $(printpassfail)
	ligolw_print inspiral_event_id_test_in2.xml >/dev/null && $(printpassfail)
	@echo "<=== end $@ ==="

ligolw_test03c :
	@echo "=== start $@ ===>"
	# test reading compressed and non-compressed files from http:// URLs
	$(servefilestart) && { ligolw_print http://127.0.0.1:$(SERVEFILESPORT)/inspiral_event_id_test_in1.xml.gz >/dev/null && $(printpassfail) ; $(servefilestop) ; }
	$(servefilestart) && { ligolw_print http://127.0.0.1:$(SERVEFILESPORT)/inspiral_event_id_test_in2.xml >/dev/null && $(printpassfail) ; $(servefilestop) ; }
	@echo "<=== end $@ ==="

ligolw_test04 :
	@echo "=== start $@ ===>"
	{ ligolw_cut --delete-table sngl_inspiral <inspiral_event_id_test_in1.xml.gz | cmp ligolw_cut_proof.xml ; } && $(printpassfail)
	@echo "<=== end $@ ==="

ligolw_test05 :
	@echo "=== start $@ ===>"
	# make sure XML writing code compresses files
	FILENAME=$(shell mktemp --suffix .xml.gz) && { ligolw_add --output $${FILENAME} ligolw_sqlite_test_input.xml.gz && gunzip --test $${FILENAME} && $(printpassfail) ; } ; rm -f $${FILENAME}
	@echo "<=== end $@ ==="

ligolw_print_test ligolw_sqlite_test :
	@echo "=== start $@ ===>"
	sh $@.sh && $(printpassfail)
	@echo "<=== end $@ ==="

ligo_lw_test_01 test_array test_ilwd test_ligolw test_lsctables test_param test_table test_tokenizer test_utils test_utils_process test_utils_segments :
	@echo "=== start $@ ===>"
	$(PYTHON) $@.py && $(printpassfail)
	@echo "<=== end $@ ==="

clean :
	rm -f ligo_lw_test_01*png
