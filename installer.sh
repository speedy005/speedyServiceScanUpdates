#!/bin/bash
######### Only This 2 lines to edit with new version ######
# Version und changelog aus der version.txt-Datei herunterladen
version=$(curl -s https://raw.githubusercontent.com/speedy005/speedyServiceScanUpdates/main/version.txt)
changelog=$(curl -s https://raw.githubusercontent.com/speedy005/speedyServiceScanUpdates/main/changelog.txt)
##############################################################

TMPPATH=/tmp/ServiceScanUpdates

# Bestimmen des Installationspfads basierend auf dem Systemtyp
if [ ! -d /usr/lib64 ]; then
	PLUGINPATH=/usr/lib/enigma2/python/Plugins/Extensions/speedyServiceScanUpdates
else
	PLUGINPATH=/usr/lib64/enigma2/python/Plugins/Extensions/speedyServiceScanUpdates
fi

# Überprüfung des OS-Typs (DreamOs oder Dream)
if [ -f /var/lib/dpkg/status ]; then
   STATUS=/var/lib/dpkg/status
   OSTYPE=DreamOs
else
   STATUS=/var/lib/opkg/status
   OSTYPE=Dream
fi
echo ""
if python --version 2>&1 | grep -q '^Python 3\.'; then
	echo "You have Python3 image"
	PYTHON=PY3
	Packagesix=python3-six
	Packagerequests=python3-requests
else
	echo "You have Python2 image"
	PYTHON=PY2
	Packagerequests=python-requests
fi

# Überprüfung und Installation der benötigten Pakete
if [ $PYTHON = "PY3" ]; then
	if ! grep -qs "Package: $Packagesix" $STATUS; then
		opkg update && opkg install python3-six
	fi
fi
echo ""
if ! grep -qs "Package: $Packagerequests" $STATUS; then
	echo "Need to install $Packagerequests"
	if [ $OSTYPE = "DreamOs" ]; then
		apt-get update && apt-get install python-requests -y
	elif [ $PYTHON = "PY3" ]; then
		opkg update && opkg install python3-requests
	elif [ $PYTHON = "PY2" ]; then
		opkg update && opkg install python-requests
	fi
fi
echo ""

# Temporäres Verzeichnis und alte Plugin-Verzeichnisse entfernen
[ -r $TMPPATH ] && rm -f $TMPPATH > /dev/null 2>&1
[ -r $PLUGINPATH ] && rm -rf $PLUGINPATH

# Erstellen des temporären Verzeichnisses und Herunterladen des Plugins
mkdir -p $TMPPATH
cd $TMPPATH
set -e

if [ -f /var/lib/dpkg/status ]; then
   echo "# Your image is OE2.5/2.6 #"
else
   echo "# Your image is OE2.0 #"
fi

# Plugin herunterladen
wget https://github.com/speedy005/speedyServiceScanUpdates/archive/refs/heads/main.tar.gz || { echo "Download failed"; exit 1; }
tar -xzf main.tar.gz
cp -r 'speedyServiceScanUpdates-main/usr' '/'

set +e
cd
sleep 2

# Überprüfen, ob das Plugin korrekt installiert wurde
if [ ! -d $PLUGINPATH ]; then
	echo "Something went wrong .. Plugin not installed"
	exit 1
fi

rm -rf $TMPPATH > /dev/null 2>&1
sync

# Ausgabe der Installationsmeldung
echo ""
echo "#########################################################"
echo "#           INSTALLED SUCCESSFULLY      #"
echo "#                  developed by speedy005                   #"
echo "#                   Big thanks speedy005                    #"
echo "#                  .::speedyServiceScanUpdates::.                  #"
echo "#                  https://Sat-Club.EU                  #"
echo "#########################################################"
echo "#           Your Device will RESTART Now                #"
echo "#########################################################"
sleep 5
killall -9 enigma2
exit 0
