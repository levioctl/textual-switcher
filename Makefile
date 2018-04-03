KEY_COMBINATION="<Control><Alt>w"
INSTALL_DIR=/usr/share/textual-switcher
LOCKFILE_PATH="/run/user/$$UID/textual-switcher.pid"
KEY_BINDING="${INSTALL_DIR}/launch"
CHROME_EXTENSION_ID=ebgonmbbfgmoiklncphoekdfkfeaenee

.PHONY: install
install: launch
	@echo Installing required packages...
	@./install-prerequisites.sh
	@echo Installing switcher scripts...
	@sudo mkdir -p ${INSTALL_DIR}
	@sudo cp switcher.py windowcontrol.py listfilter.py tabcontrol.py pidfile.py glib_wrappers.py launch browser-agent/api_proxy_native_app.py ${INSTALL_DIR}
	@echo Creating PID file...
	@touch ${LOCKFILE_PATH}
	@sudo chmod 777 ${LOCKFILE_PATH}
	@echo Setting the keyboard shortcut...
	@$(MAKE) install_firefox_extension
	@$(MAKE) install_chrome_extension
	@python apply-binding.py ${KEY_BINDING} ${KEY_COMBINATION}
	@echo "Done. Press " ${KEY_COMBINATION} " to launch the switcher (you might need to restart for the binding to work)."

launch: launch.c
	@gcc -Wall -Werror -pedantic -std=c99 launch.c -o launch

.PHONY: install_firefox_extension
install_firefox_extension:
	@echo Installing the Firefox extension...
	@mkdir -p ~/.mozilla/extensions/{\ec8030f7-c20a-464f-9b0e-13a3a9e97384\}/
	@cp browser-agent/firefox-tablister-extension/textual_switcher_agent-1.0-an+fx.xpi ~/.mozilla/extensions/\{ec8030f7-c20a-464f-9b0e-13a3a9e97384\}/{c60f517c-ccd3-4ec2-a289-0d9fe8e3cdf5}.xpi
	@echo Installing the API proxy manifest for the Firefox extension...
	@mkdir -p ~/.mozilla/native-messaging-hosts/
	@cp browser-agent/firefox-tablister-extension/api_proxy_native_app.json ~/.mozilla/native-messaging-hosts/

.PHONY: install_chrome_extension
install_chrome_extension:
	@echo Installing the Chrome extension...
	@mkdir -p /usr/share/google-chrome/extensions/
	@sudo cp browser-agent/chrome-tablister-extension/preferences-file.json /usr/share/google-chrome/extensions/${CHROME_EXTENSION_ID}.json
	@sudo chmod +r /usr/share/google-chrome/extensions/${CHROME_EXTENSION_ID}.json
	@echo Installing the API proxy manifest for the Chrome extension...
	@mkdir -p ~/.config/google-chrome/NativeMessagingHosts/
	@cp browser-agent/chrome-tablister-extension/api_proxy_native_app.json ~/.config/google-chrome/NativeMessagingHosts/
