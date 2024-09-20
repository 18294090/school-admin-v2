cd /home/zh/school-admin-v2/venv/bin
source activate
cd /home/zh/school-admin-v2
export FLASK_APP=main.py
export FLASK_DEBUG=1
uwsgi myapp.ini
