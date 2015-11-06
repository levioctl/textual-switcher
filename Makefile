KEY_COMBINATION="<Primary><Alt>w" # Ctrl+Alt+w
INSTALL_DIR="/usr/share/textual-switcher"


.PHONY: install
install:
	./install-prerequisites.sh
	sudo mkdir -p ${INSTALL_DIR}
	sudo cp switcher.py ${INSTALL_DIR}
	sudo python apply-binding.py ${INSTALL_DIR}/switcher.py ${KEY_COMBINATION}
	@echo "Done. Press " ${KEY_COMBINATION} " to launch the switcher."

run:
	python switcher.py
