#!/bin/bash
echo "Construindo executável do Sistema de Controle de Testes..."
echo

pyinstaller --name="SistemaControleTestes" \
    --onefile \
    --add-data="templates:templates" \
    --add-data="static:static" \
    --noconsole \
    main.py

echo
echo "✅ Executável criado com sucesso!"
echo "📁 O arquivo está na pasta: dist/SistemaControleTestes"
echo