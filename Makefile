KEY_COMBINATION="<Control><Alt>w"
INSTALL_DIR="/usr/share/textual-switcher"
LOCKFILE_PATH="/run/lock/textual_switcher.xid"
KEY_BINDING="/bin/bash -c \"\ (wmctrl -l | grep \\\`cat ${LOCKFILE_PATH}\\\` && wmctrl -iR \\\`cat ${LOCKFILE_PATH}\\\` ) || /usr/bin/python ${INSTALL_DIR}/switcher.py ${LOCKFILE_PATH}\""

.PHONY: install
install:
	./install-prerequisites.sh
	sudo mkdir -p ${INSTALL_DIR}
	sudo cp switcher.py ${INSTALL_DIR}
	sudo touch ${LOCKFILE_PATH}
	sudo chmod 777 ${LOCKFILE_PATH}
	python apply-binding.py ${KEY_BINDING} ${KEY_COMBINATION}
	@echo "Done. Press " ${KEY_COMBINATION} " to launch the switcher (you might need to restart for the binding to work)."

run:
	python switcher.py
