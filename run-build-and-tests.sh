#! /bin/bash

set -e

CWD=$(pwd)
APPDIR="$(pwd)/latex2image"

sudo apt-get update
sudo apt-get -y install --no-install-recommends -qq wget curl imagemagick
sudo apt-get -y install --no-install-recommends -qq $(awk '{print $1'} texlive_apt.list)
tex --version
echo codecov >> "$APPDIR"/requirements.txt
echo factory_boy >> "$APPDIR"/requirements.txt
pip install --no-cache-dir -r "$APPDIR"/requirements.txt
yes | sudo rm /etc/ImageMagick*/policy.xml # https://stackoverflow.com/a/54230833/3437454

# if you need to install extra packages, specify in EXTRA_PACKAGE in Travis options.
if [[ "$EXTRA_PACKAGE" ]]
then
  sudo apt-get -y install --no-install-recommends -qq "$EXTRA_PACKAGE"
fi

# Install extra fonts. Compress the fonts you want to include in you own build, and
# make the file a downloadable link with ".tar.gz" extensions, and the put
# the url in your Travis-CI env named "$MY_EXTRA_FONTS_GZ".

# ALERT!!! To include fonts in your own builds, You must respect the intellectual property
# rights (LICENSE) of those fonts, and take the correspond legal responsibility.

sudo mkdir -p ./extra_fonts

if [[ "$MY_EXTRA_FONTS_GZ" ]]
then
  echo "----Installing user customized fonts.----"
  wget "$MY_EXTRA_FONTS_GZ" -O fonts.tar.gz -q
  sudo mkdir -p /usr/share/fonts/extra_fonts
  sudo tar -zxf fonts.tar.gz -C ./extra_fonts
  sudo cp -r ./extra_fonts /usr/share/fonts/
  sudo fc-cache -f
else
  echo "----No user customized fonts.----"
fi

# This is needed to run makemigrations
cd "$APPDIR" || exit 1
cp local_settings/local_settings_example.py local_settings/local_settings.py
npm install
python manage.py collectstatic

if [[ $DOCKER_USERNAME ]]; then
echo "----Building docker image.----"
cd "$CWD" || exit 1
docker build --no-cache . -t $DOCKER_USERNAME/latex2image:${TRAVIS_COMMIT::8} || exit 1

echo "----Docker images----"
docker images
fi

cd "$APPDIR" || exit 1
python manage.py makemigrations

echo "----Tests started:----"
coverage run manage.py test tests && coverage report -m && codecov
