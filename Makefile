KEY_COMBINATION="<Control><Alt>w"
INSTALL_DIR=/usr/share/textual-switcher
LOCKFILE_PATH="/run/lock/textual_switcher.pid"
KEY_BINDING="${INSTALL_DIR}/launch"

.PHONY: install
install: launch
	./install-prerequisites.sh
	sudo mkdir -p ${INSTALL_DIR}
	sudo cp switcher.py windowcontrol.py listfilter.py tabcontrol.py pidfile.py glib_wrappers.py launch ${INSTALL_DIR}
	sudo touch ${LOCKFILE_PATH}
	sudo chmod 777 ${LOCKFILE_PATH}
	sudo pip install fuzzywuzzy expiringdict
	python apply-binding.py ${KEY_BINDING} ${KEY_COMBINATION}
	@echo "Done. Press " ${KEY_COMBINATION} " to launch the switcher (you might need to restart for the binding to work)."

launch: launch.c
	gcc -Wall -Werror -pedantic -std=c99 launch.c -o launch
