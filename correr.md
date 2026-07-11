
# SERVER
python main.py --host 0.0.0.0 --port 8000


# CLIENTE

python cliente.py moderate 127.0.0.1:8000 "hola mundo"
python cliente.py allowed 127.0.0.1:8000
python cliente.py bloqued 127.0.0.1:8000
python cliente.py error400 127.0.0.1:8000
python cliente.py error500 127.0.0.1:8000
python cliente.py all 127.0.0.1:8000