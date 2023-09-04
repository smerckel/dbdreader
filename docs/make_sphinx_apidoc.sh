#!/bin/bash

sphinx-apidoc -f -o source/ ../ ../setup.py ../tests/*.py ../examples/*.py
