# Makefile for Sphinx documentation
#

SPHINXBUILD = sphinx-build
BUILDDIR    = _build
SPHINXOPTS  = -d $(BUILDDIR)/doctrees .

.PHONY: all html clean html install

all: html

html:
	$(SPHINXBUILD) -b html $(SPHINXOPTS) $(BUILDDIR)/html

clean:
	-rm -rf $(BUILDDIR)/*

install: html
	cp -pr  $(BUILDDIR)/html/* $(INSTALLDIR)/.

tarball: html
	cd $(BUILDDIR)/html  && tar cvzf ../../../_doc.tgz *
