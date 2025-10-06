@echo off
echo Construindo Sistema de Controle de Testes...
echo.

pyinstaller --onefile ^
    --name="SistemaControleTestes" ^
    --add-data="templates;templates" ^
    --add-data="static;static" ^
    --hidden-import="sqlalchemy.sql.default_comparator" ^
    --hidden-import="flask_login" ^
    --hidden-import="flask_sqlalchemy" ^
    --hidden-import="weasyprint" ^
    --hidden-import="cairo" ^
    --hidden-import="cffi" ^
    --hidden-import="markupsafe" ^
    --noconsole ^
    main.py

echo.
echo ✅ Executável criado: dist\SistemaControleTestes.exe
echo.
pause