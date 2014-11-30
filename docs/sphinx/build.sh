#!/bin/bash

export PYTHONPATH=$PWD/../..

function installdeps(){
    sudo apt-get install \
        python-blockdiag \
        python-sphinx \
        texlive-latex-base \
        texlive-latex-extra \
        python-sphinxcontrib.actdiag \
        python-sphinxcontrib.blockdiag \
        python-sphinxcontrib.nwdiag \
        python-sphinxcontrib.seqdiag \
        python-sphinxcontrib.spelling \
        fonts-droid \
        python-reportlab
}

function clean(){
    rm -rf _build
}

function html(){
    make html
}

function pdf(){
    make latexpdf
}

$@