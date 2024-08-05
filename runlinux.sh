cd /home/zh/web/intelligent-school/venv/bin
source activate
cd /home/zh/web/intelligent-school
export FLASK_APP=main.py
export FLASK_DEBUG=1
flask run --host="0.0.0.0" --port="5000"