KEY_COMBINATION="<Control><Alt>w"
INSTALL_DIR="/usr/share/textual-switcher"


.PHONY: install
install:
	./install-prerequisites.sh
	sudo mkdir -p ${INSTALL_DIR}
	sudo cp switcher.py ${INSTALL_DIR}
	python apply-binding.py ${INSTALL_DIR}/switcher.py ${KEY_COMBINATION} 
	@echo "Done. Press " ${KEY_COMBINATION} " to launch the switcher (you might need to restart for the binding to work)."

run:
	python switcher.py
