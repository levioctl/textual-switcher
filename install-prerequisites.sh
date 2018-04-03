#!/bin/bash

# Determine package manager
OS=`grep ^NAME /etc/os-release | cut -d '=' -f 2`
OS=`sed -e 's/^"//' -e 's/"$//' <<<"$OS"`
COMMON_PACKAGES="
	wmctrl
"
if [ "$OS" = "Fedora" ]
then
	PKG_MGR_CMD="sudo yum install -y"
	PACKAGES="
		dconf
		pygobject3-devel
	"
elif [ "$OS" = "Ubuntu" ]
then
	PKG_MGR_CMD="sudo apt-get install -y"
	PACKAGES="dconf-cli"
else
	echo "Error: Package manager was not found."
	exit 1;
fi

${PKG_MGR_CMD} ${COMMON_PACKAGES} ${PACKAGES}

sudo pip install fuzzywuzzy expiringdict python-Levenshtein
