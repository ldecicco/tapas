PROG := python-hls-player
PYTHON := python2.7
#KEY := $(shell LANG=C python2.7 ../../scripts/gethwkey)
#
REV := $(shell LANG=C git rev-parse HEAD)
#
PROG_PY := $(wildcard player/*.py)
PROG_SO := $(patsubst player/%.py, player/%.so, $(PROG_PY))
#

all: $(PROG)

%.so: %.py
	../scripts/python-compile $(PYTHON) $^

hlsplayer: hlsplayer.py
	../scripts/python-compile $(PYTHON) $^ exec

$(PROG): $(PROG_SO) hlsplayer
	rm -rf $(PROG)
	mkdir $(PROG)
	#
	mkdir $(PROG)/player
	cp player/*.so $(PROG)/player
	cat player/__init__.py | sed -e 's/__version__ = "dev"/__version__ = "$(REV)"/' > $(PROG)/player/__init__.py
	#
	cp hlsplayer $(PROG)

deb:
	dpkg-buildpackage -rfakeroot -sd -us -uc -j9 -b

clean:
	rm -f $(PROG_SO) hlsplayer
	rm -rf $(PROG)
	find . -name '*.py[co]' -exec rm -f {} \;
	fakeroot debian/rules clean
