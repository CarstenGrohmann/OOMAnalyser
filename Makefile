# Makefile for OOMAnalyser
#
# Copyright (c) 2017-2020 Carsten Grohmann
# License: MIT (see LICENSE.txt)
# THIS PROGRAM COMES WITH NO WARRANTY

.PHONY: help clean distclean

# Makefile defaults
SHELL             = /bin/sh

BASE_DIR          = .
PYTHON3_BIN       = python3
VIRTUAL_ENV       = env

export VIRTUAL_ENV := $(abspath ${VIRTUAL_ENV})
export PATH := ${VIRTUAL_ENV}/bin:${PATH}

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

#+ Clean python compiler files and automatically generated files
clean:
	@echo "Remove all automatically generated files ..."
	@find $(BASE_DIR) -depth -type f -name "*.pyc" -exec rm -f {} \;
	@find $(BASE_DIR) -depth -type f -name "*.pyo" -exec rm -f {} \;
	@find $(BASE_DIR) -depth -type f -name "*.orig" -exec rm -f {} \;
	@find $(BASE_DIR) -depth -type f -name "*~" -exec rm -f {} \;
	@$(RM) --force --recursive __javascript__

#+ Remove all automatically generated and Git repository data
distclean: clean venv-clean
	@echo "Remove Git repository data (.git*) ..."
	@(RM) --force .git .gitignore

$(VIRTUAL_ENV)/bin/activate: requirements.txt
	test -d $(VIRTUAL_ENV) || virtualenv $(VIRTUAL_ENV)
	. $(VIRTUAL_ENV)/bin/activate
	$(VIRTUAL_ENV)/bin/pip install -Ur requirements.txt
	touch $(VIRTUAL_ENV)/bin/activate

#+ Setup the virtual environment from scratch
venv: $(VIRTUAL_ENV)/bin/activate

#+ Freeze the current virtual environment by update requirements.txt
venv-freeze:
	source $(VIRTUAL_ENV)/bin/activate && $(VIRTUAL_ENV)/bin/pip freeze > requirements.txt

#+ Remove the virtual environment
venv-clean:
	rm -rf $(VIRTUAL_ENV)

#+ Compile Python to JavaScript
build: venv
	. $(VIRTUAL_ENV)/bin/activate
	transcrypt --build --map --nomin -e 6 OOMAnalyser.py

#+ Serve the current directory on http://127.0.0.1:8080
websrv:
	$(PYTHON3_BIN) -m http.server 8080 --bind 127.0.0.1