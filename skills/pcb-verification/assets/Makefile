# Verification Makefile of a board: skeleton to copy into <board>/verification/Makefile. One target per check.
# Scripts that read the board run with KiCad's Python (pcbnew); scripts that compute run with the venv.
KICAD_CLI ?= /Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
KICAD_PY  ?= /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
LIB       ?= ../../../verification-lib
VENV_PY   ?= $(LIB)/.venv/bin/python
BOARD     := $(basename $(wildcard ../*.kicad_pcb))
# KiCad writes its settings when it exits: it runs on a copy of the user's configuration, never on it
KICAD_CFG ?= $(HOME)/Library/Preferences/kicad
export KICAD_CONFIG_HOME := $(CURDIR)/results/kicad_config
export PYTHONDONTWRITEBYTECODE := 1
# pcbnew noise filtered; pipefail keeps the script's status (GNU Make 3.81 ignores .SHELLFLAGS)
QUIET     := 2>&1 | sed -E '/Fontconfig|Debug:|assert/d'
SHELL     := /bin/bash -e -o pipefail

.PHONY: all check straps impedance_board audit report

# The order of `all` matters: no `make -j`. `report` comes last and reads results/ only.
all: check straps impedance_board audit report

$(KICAD_CONFIG_HOME):
	mkdir -p $@ && cp -R "$(KICAD_CFG)/." $@

# Stored zone fills against a refill, then complete ERC/DRC reports, then failure on errors only
check: | $(KICAD_CONFIG_HOME)
	$(KICAD_PY) $(LIB)/fills_check.py $(BOARD).kicad_pcb $(QUIET)
	$(KICAD_CLI) sch erc --severity-all --format json -o results/erc.json $(BOARD).kicad_sch
	$(KICAD_CLI) pcb drc --severity-all --schematic-parity --format json --units mm -o results/drc.json $(BOARD).kicad_pcb
	$(KICAD_CLI) sch erc --severity-error --exit-code-violations -o /dev/null $(BOARD).kicad_sch
	$(KICAD_CLI) pcb drc --severity-error --schematic-parity --exit-code-violations -o /dev/null $(BOARD).kicad_pcb

# A check that reads the board
straps: | $(KICAD_CONFIG_HOME)
	cd scripts && $(KICAD_PY) straps.py $(QUIET)

# Extraction from the board, then computation
impedance_board: | $(KICAD_CONFIG_HOME)
	cd scripts && $(KICAD_PY) impedance_extract.py $(QUIET)
	cd scripts && $(VENV_PY) impedance_board.py

audit: impedance_board
	cd scripts && $(KICAD_PY) layout_audit.py $(QUIET)

report:
	cd scripts && $(VENV_PY) report.py
