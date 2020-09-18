#!/bin/sh
git clone https://github.com/avih/dejsonlz4 dejsonlz4-repo
cd dejsonlz4-repo && gcc -Wall -o dejsonlz4 src/dejsonlz4.c src/lz4.c && cd -
cp -f dejsonlz4-repo/dejsonlz4 .
