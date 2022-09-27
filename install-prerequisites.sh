#!/bin/bash

# Exit on first error
set -e

# Determine package manager
OS=`grep ^NAME /etc/os-release | cut -d '=' -f 2`
OS=`sed -e 's/^"//' -e 's/"$//' <<<"$OS"`
COMMON_PACKAGES="
	wmctrl
"
if [ "$OS" = "Fedora" ]
then
	PKG_MGR_CMD="sudo dnf install -y"
	PACKAGES="
		dconf
		pygobject3-devel
	"
elif [ "$OS" = "Ubuntu" ]
then
	PKG_MGR_CMD="sudo apt-get install -y"
	PACKAGES="
		dconf-cli
		python-gi-dev
		python3-pip
		libpython3-dev
	"
elif [ "$OS" = "Linux Mint" ]
then
	PKG_MGR_CMD="sudo apt-get install -y"
	PACKAGES="
		dconf-cli
		python-gi-dev
                build-essential
		python3-pip
		libpython3-dev
	"
else
	echo "Error: Package manager was not found."
	exit 1;
fi

echo Installing required packages...
${PKG_MGR_CMD} ${COMMON_PACKAGES} ${PACKAGES}

echo Installing required python libraries...
sudo pip3 install setuptools
sudo pip3 install -r requirements.txt
