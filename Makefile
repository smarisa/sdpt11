# Neronet makefile
#
# Variables
SPHINXOPTS = -d ./doc/build/doctrees ./doc/source

.PHONY: help clean codedoc artifacts

help:
	@echo "Please use 'make <target>' where <target> is one of"
	@echo "  codedoc       to generate HTML code documentation"
	@echo "  artifacts     to compile all artifacts to PDF"

clean:
	rm -rf ./doc/build/*

codedoc:
	sphinx-build -b html $(SPHINXOPTS) ./doc/build/html
	@echo
	@echo "Build finished. The HTML pages are in ./doc/build/html."

artifacts:
	@echo "Compiling all updated artifacts."
	cd ./doc
	cpdfs ./*.md ./*.tex
	zip ./required_artifacts.zip \
	  ./product_vision.pdf \
	  ./process_overview.pdf \
	  ./technical_overview.pdf \
	  ./definition_of_done.pdf \
	  ./progress_report.pdf \
	  ./test_session_charter.pdf
	@echo "Compilation finished."
