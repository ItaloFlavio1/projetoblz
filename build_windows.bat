@echo off
chcp 65001 >nul
echo ===============================================
echo  CONSTRUINDO EXECUTÁVEL PARA WINDOWS
echo ===============================================
echo.

echo 1. Instalando PyInstaller...
pip install pyinstaller

echo.
echo 2. Construindo executável...
pyinstaller --onefile ^
    --name "SistemaControleTestes" ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    --hidden-import "sqlalchemy.sql.default_comparator" ^
    --hidden-import "flask_login" ^
    --hidden-import "flask_sqlalchemy" ^
    --hidden-import "weasyprint" ^
    --hidden-import "cairo" ^
    --hidden-import "cffi" ^
    --hidden-import "markupsafe" ^
    --hidden-import "jinja2" ^
    --hidden-import "werkzeug.security" ^
    --noconsole ^
    main.py

echo.
echo ===============================================
echo ✅ EXECUTÁVEL CRIADO COM SUCESSO!
echo ===============================================
echo.
echo 📍 Arquivo: dist\SistemaControleTestes.exe
echo.
echo 🚀 PARA USAR:
echo    1. Execute dist\SistemaControleTestes.exe
echo    2. Aguarde o navegador abrir
echo    3. Login: admin / admin
echo.
echo ⚠️  Nota: Na primeira execução, o Windows Defender pode
echo     alertar sobre aplicação não reconhecida.
echo     Clique em 'Mais informações' e 'Executar mesmo assim'
echo.
pause