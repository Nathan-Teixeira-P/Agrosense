#!/usr/bin/env bash
cd "$(dirname "$0")" || exit 1
python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' || { echo "Preciso de Python 3.10+"; exit 1; }
grep -q '^OPENAI_API_KEY=.\+' .env 2>/dev/null || { echo "Falta OPENAI_API_KEY no arquivo .env"; exit 1; }
porta=$(ls /dev/ttyACM* /dev/ttyUSB* 2>/dev/null | head -1)
echo "Porta serial: ${porta:-nenhuma (use o modo Demonstracao)}"
(sleep 2; xdg-open http://localhost:3000 >/dev/null 2>&1) &
exec python3 server.py
