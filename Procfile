web: python manage.py collectstatic --noinput && gunicorn config.wsgi --log-file -
release: python manage.py migrate --noinput
