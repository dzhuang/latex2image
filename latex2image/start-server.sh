#!/usr/bin/env bash

USER_REQUIREMENTS=/opt/latex2image/local_settings/requirements.txt
if test -f "$USER_REQUIREMENTS"; then
    pip install -r $USER_REQUIREMENTS
fi

python manage.py makemigrations
python manage.py migrate --noinput

python manage.py createsuperuser --no-input

(gunicorn latex2image.wsgi --user l2i_user --bind 0.0.0.0:8010 --workers 3) &
sudo nginx
