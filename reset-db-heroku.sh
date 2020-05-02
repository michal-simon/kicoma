# redeploy
# git push heroku master

# reset DB
heroku restart
heroku pg:reset DATABASE --confirm kicoma
heroku run python manage.py makemigrations
heroku run python manage.py migrate
heroku run python manage.py createsuperuser --username admin

# initialize DB from fixtures
heroku run python manage.py loaddata kicoma/kitchen/fixtures/druhy-jidla.json
heroku run python manage.py loaddata kicoma/kitchen/fixtures/alergeny.json
heroku run python manage.py loaddata kicoma/kitchen/fixtures/jednotky.json
heroku run python manage.py loaddata kicoma/kitchen/fixtures/dph.json
heroku run python manage.py loaddata kicoma/kitchen/fixtures/skupiny-stravniku.json
heroku run python manage.py loaddata kicoma/kitchen/fixtures/skupiny.json
heroku run python manage.py loaddata kicoma/kitchen/fixtures/uzivatele.json