# -*- coding: utf-8 -*-
"""
Sistema de Controle de Testes - Versão Online

Este script é o ponto de entrada para a aplicação em um ambiente de produção.
Ele inicializa o banco de dados, cria um usuário administrador padrão (se não existir)
e inicia o servidor Flask otimizado para implantação em serviços de nuvem.
"""
import os
import sys
import threading
from datetime import datetime, date, timezone, timedelta

# Adiciona o diretório atual ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def get_brasil_datetime():
    """Retorna o datetime atual no fuso horário de São Paulo (UTC-3).

    Returns:
        datetime: O objeto datetime com o fuso horário de São Paulo.
    """
    brasil_tz = timezone(timedelta(hours=-3))
    return datetime.now(brasil_tz)

def main():
    """Função principal para produção.

    Esta função realiza as seguintes etapas:
    1. Importa as dependências necessárias da aplicação principal.
    2. Inicializa o banco de dados, criando as tabelas se não existirem.
    3. Cria um usuário 'admin' padrão se nenhum usuário com esse nome existir.
    4. Configura o host e a porta para o servidor, priorizando variáveis de ambiente.
    5. Inicia o servidor Flask em modo de produção (sem debug).
    """
    from app import app, db, User, safe_commit

    print("=" * 50)
    print("🚀 SISTEMA CONTROLE TESTES - INICIANDO")
    print("=" * 50)

    # Inicializa banco de dados
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username="admin").first():
            admin_user = User(username="admin", role="admin")
            admin_user.set_password("admin")
            db.session.add(admin_user)
            safe_commit()
            print("✅ Usuário admin criado (admin/admin)")

    # Configurações para produção
    port = int(os.environ.get('PORT', 5000))
    host = '0.0.0.0'  # Importante para serviços cloud

    print(f"🌐 Servidor iniciando...")
    print(f"📍 Acesse: http://seu-dominio.onrender.com")
    print("-" * 50)

    # Inicia servidor
    app.run(
        host=host,
        port=port,
        debug=False,
        threaded=True
    )

if __name__ == "__main__":
    main()
