check : \
	ligolw_sqlite_test \
	ligolw_test01 \
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
	test_utils_segments
	@echo "All Tests Passed"

define printpassfail
{ echo "Pass" ; true ; } || { echo "Fail" ; false ; }
endef

SERVEFILESPORT := 16543

define servefilesstart
{ python -c "import SocketServer, SimpleHTTPServer ; SocketServer.TCPServer(('127.0.0.1', $(SERVEFILESPORT)), SimpleHTTPServer.SimpleHTTPRequestHandler).handle_request()" & sleep 1 ; }
endef
define servefilesstop
wait
endef

ligolw_test01 :
	@echo "=== start ligolw_test01 ===>"
	# test reading array data from a file
	python ligo_lw_test_01.py && $(printpassfail)
	@echo "<=== end ligolw_test01 ==="

ligolw_test03a :
	@echo "=== start ligolw_test03a ===>"
	# test reading compressed and non-compressed files from stdin
	{ cat inspiral_event_id_test_in1.xml.gz | ligolw_print >/dev/null ; } && $(printpassfail)
	{ cat inspiral_event_id_test_in2.xml | ligolw_print >/dev/null ; } && $(printpassfail)
	@echo "<=== end ligolw_test03a ==="

ligolw_test03b :
	@echo "=== start ligolw_test03b ===>"
	# test reading compressed and non-compressed files
	ligolw_print inspiral_event_id_test_in1.xml.gz >/dev/null && $(printpassfail)
	ligolw_print inspiral_event_id_test_in2.xml >/dev/null && $(printpassfail)
	@echo "<=== end ligolw_test03b ==="

ligolw_test03c :
	@echo "=== start ligolw_test03c ===>"
	# test reading compressed and non-compressed files from http:// URLs
	$(servefilesstart) && { ligolw_print http://127.0.0.1:$(SERVEFILESPORT)/inspiral_event_id_test_in1.xml.gz >/dev/null && $(printpassfail) ; } ; $(servefilesstop)
	$(servefilesstart) && { ligolw_print http://127.0.0.1:$(SERVEFILESPORT)/inspiral_event_id_test_in2.xml >/dev/null && $(printpassfail) ; } ; $(servefilesstop)
	@echo "<=== end ligolw_test03c ==="

ligolw_test04 :
	@echo "=== start ligolw_test04 ===>"
	{ ligolw_cut --delete-table sngl_inspiral <inspiral_event_id_test_in1.xml.gz | cmp ligolw_cut_proof.xml ; } && $(printpassfail)
	@echo "<=== end ligolw_test04 ==="

ligolw_test05 :
	@echo "=== start ligolw_test05 ===>"
	# make sure XML writing code compresses files
	FILENAME=$(shell mktemp --suffix .xml.gz) && { ligolw_add --output $${FILENAME} ligolw_sqlite_test_input.xml.gz && gunzip --test $${FILENAME} && $(printpassfail) ; } ; rm -f $${FILENAME}
	@echo "<=== end ligolw_test05 ==="

ligolw_sqlite_test :
	@echo "=== start ligolw_sqlite_test ===>"
	sh ligolw_sqlite_test.sh && $(printpassfail)
	@echo "<=== end ligolw_sqlite_test ==="

test_array :
	@echo "=== start test_array ===>"
	./test_array.py && $(printpassfail)
	@echo "<=== end test_array ==="

test_ilwd :
	@echo "=== start test_ilwd ===>"
	python test_ilwd.py && $(printpassfail)
	@echo "<=== end test_ilwd ==="

test_ligolw :
	@echo "=== start test_ligolw ===>"
	./test_ligolw.py && $(printpassfail)
	@echo "<=== end test_ligolw ==="

test_lsctables :
	@echo "=== start test_lsctables ===>"
	./test_lsctables.py && $(printpassfail)
	@echo "<=== end test_lsctables ==="

test_param :
	@echo "=== start test_param ===>"
	./test_param.py && $(printpassfail)
	@echo "<=== end test_param ==="

test_table :
	@echo "=== start test_table ===>"
	./test_table.py && $(printpassfail)
	@echo "<=== end test_table ==="

test_tokenizer :
	@echo "=== start test_tokenizer ===>"
	./test_tokenizer.py && $(printpassfail)
	@echo "<=== end test_tokenizer ==="

test_utils :
	@echo "=== start test_utils ===>"
	./test_utils.py && $(printpassfail)
	@echo "<=== end test_utils ==="

test_utils_segments :
	@echo "=== start test_utils_segments ===>"
	./test_utils_segments.py && $(printpassfail)
	@echo "<=== end test_utils_segments ==="

clean :
	rm -f ligo_lw_test_01*png
