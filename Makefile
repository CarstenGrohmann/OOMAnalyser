# Makefile for OOMAnalyser
#
# Copyright (c) 2017-2023 Carsten Grohmann
# License: MIT (see LICENSE.txt)
# THIS PROGRAM COMES WITH NO WARRANTY

.PHONY: help clean distclean venv venv-clean venv-freeze build websrv test

# Makefile defaults
SHELL             = /bin/sh

BASE_DIR          = .
PYTHON3_BIN       = /usr/bin/python3.7
TARGET_DIR        = $(BASE_DIR)/__target__
VIRTUAL_ENV_DIR   = env

HTML_FILE         = $(BASE_DIR)/OOMAnalyser.html
JS_OUT_FILE       = $(BASE_DIR)/OOMAnalyser.js
JS_TEMP_FILE      = $(TARGET_DIR)/OOMAnalyser.js
PY_SOURCE         = $(BASE_DIR)/OOMAnalyser.py
TEST_FILE         = $(BASE_DIR)/test.py

# e.g. 0.6.0 or 0.6.0_devel
VERSION           = 0.6.0_devel
RELEASE_DIR       = $(BASE_DIR)/release
RELEASE_FILES     = $(HTML_FILE) $(JS_OUT_FILE) $(PY_SOURCE) $(TEST_FILE) rollup.config.mjs Makefile requirements.txt \
				    LICENSE.txt  README.md
RELEASE_INST_DIR  = $(RELEASE_DIR)/OOMAnalyser-$(VERSION)
RELEASE_TARGZ     = OOMAnalyser-$(VERSION).tar.gz
RELEASE_ZIP       = OOMAnalyser-$(VERSION).zip

BLACK_BIN         = black
BLACK_OPTS        = --verbose

ROLLUP_BIN        = rollup
ROLLUP_OPTS       = --config rollup.config.mjs

TRANSCRYPT_BIN    = transcrypt
TRANSCRYPT_OPTS   = --build --map --nomin --sform --esv 6

export VIRTUAL_ENV := $(abspath ${VIRTUAL_ENV_DIR})
export PATH := ${VIRTUAL_ENV_DIR}/bin:${PATH}

HELP= @grep -B1 '^[a-zA-Z\-]*:' Makefile |\
         awk 'function p(h,t){printf"%-12s=%s\n",h,t;};\
         /\#+/{t=$$0;};\
         /:/{gsub(":.*","");h=$$0};\
         /^--/{p(h,t);t=h="";};\
         END{p(h,t)}' |\
         sed -n 's/=.*\#+/:/gp'

#+ Show this text
help:
	$(HELP)

#+ Run source code formatter black
black:
	$(BLACK_BIN) $(BLACK_OPTS) $(PY_SOURCE) $(TEST_FILE)

#+ Run source code formatter black in check-only mode
black-check:
	$(BLACK_BIN) --check $(BLACK_OPTS) $(PY_SOURCE) $(TEST_FILE)

#+ Clean python compiler files and automatically generated files
clean:
	@echo "Remove all automatically generated files ..."
	@find $(BASE_DIR) -depth -type f -name "*.pyc" -exec rm -f {} \;
	@find $(BASE_DIR) -depth -type f -name "*.pyo" -exec rm -f {} \;
	@find $(BASE_DIR) -depth -type f -name "*.orig" -exec rm -f {} \;
	@find $(BASE_DIR) -depth -type f -name "*~" -exec rm -f {} \;
	@$(RM) --force --recursive .wdm
	@$(RM) --force --recursive ${RELEASE_DIR} ${TARGET_DIR} ${RELEASE_TARGZ} ${RELEASE_ZIP}

#+ Remove all automatically generated and Git repository data
distclean: clean venv-clean
	@echo "Remove Git repository data (.git*) ..."
	@(RM) --force .git .gitignore

$(VIRTUAL_ENV_DIR)/bin/activate: requirements.txt
	test -d $(VIRTUAL_ENV_DIR) || virtualenv -p $(PYTHON3_BIN) $(VIRTUAL_ENV_DIR)
	. $(VIRTUAL_ENV_DIR)/bin/activate
	$(VIRTUAL_ENV_DIR)/bin/pip install -Ur requirements.txt
	touch $(VIRTUAL_ENV_DIR)/bin/activate

#+ Setup the virtual environment from scratch
venv: $(VIRTUAL_ENV_DIR)/bin/activate

#+ Freeze the current virtual environment by update requirements.txt
venv-freeze:
	source $(VIRTUAL_ENV_DIR)/bin/activate && $(VIRTUAL_ENV_DIR)/bin/pip freeze > requirements.txt

#+ Remove the virtual environment
venv-clean:
	rm -rf $(VIRTUAL_ENV_DIR)

${JS_TEMP_FILE}: $(VIRTUAL_ENV_DIR)/bin/activate ${PY_SOURCE}
	. $(VIRTUAL_ENV_DIR)/bin/activate
	$(TRANSCRYPT_BIN) $(TRANSCRYPT_OPTS) ${PY_SOURCE}

${JS_OUT_FILE}: $(VIRTUAL_ENV_DIR)/bin/activate ${JS_TEMP_FILE}
	. $(VIRTUAL_ENV_DIR)/bin/activate
	$(ROLLUP_BIN) $(ROLLUP_OPTS)

${RELEASE_TARGZ} ${RELEASE_ZIP}:
	mkdir -p $(RELEASE_INST_DIR) && \
	cp -p $(RELEASE_FILES) $(RELEASE_INST_DIR) && \
	cd $(RELEASE_DIR) && \
	tar cvzf $(RELEASE_TARGZ) OOMAnalyser-$(VERSION) && \
	zip -vr $(RELEASE_ZIP) OOMAnalyser-$(VERSION) && \
	mv $(RELEASE_TARGZ) $(RELEASE_ZIP) ..

#+ Compile Python to JavaScript
build: $(VIRTUAL_ENV_DIR)/bin/activate ${JS_OUT_FILE}

#+ Serve the current directory on http://127.0.0.1:8080
websrv: $(VIRTUAL_ENV_DIR)/bin/activate ${JS_OUT_FILE}
	$(PYTHON3_BIN) -m http.server 8080 --bind 127.0.0.1

#+ Run Selenium based web tests
test: $(VIRTUAL_ENV_DIR)/bin/activate ${JS_OUT_FILE}
	. $(VIRTUAL_ENV_DIR)/bin/activate
	DISPLAY=:1 xvfb-run python $(TEST_FILE)

#+ Build release packages
release: ${JS_OUT_FILE} ${RELEASE_TARGZ} ${RELEASE_ZIP}
