"""
Sistema de Controle de Testes - Executável Windows
"""
import os
import sys
import threading
import webbrowser
import time
import socket

def find_free_port():
    """Encontra uma porta livre"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

# Adiciona o diretório atual ao path
if getattr(sys, 'frozen', False):
    # Executável PyInstaller
    base_dir = sys._MEIPASS
else:
    # Script Python normal
    base_dir = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, base_dir)

def open_browser(port):
    """Abre o navegador automaticamente"""
    def _open():
        time.sleep(3)  # Aguarda o servidor iniciar
        url = f'http://127.0.0.1:{port}'
        print(f"🌐 Abrindo: {url}")
        webbrowser.open_new(url)
    
    threading.Thread(target=_open, daemon=True).start()

def main():
    """Função principal"""
    print("=" * 60)
    print("🚀 SISTEMA DE CONTROLE DE TESTES - INICIANDO")
    print("=" * 60)
    
    try:
        from app import app, db, User, safe_commit
    except ImportError as e:
        print(f"❌ Erro ao importar módulos: {e}")
        print("📦 Verifique se as dependências estão instaladas")
        input("Pressione Enter para sair...")
        return

    # Encontra porta livre
    port = find_free_port()
    
    # Inicializa banco de dados
    print("📊 Inicializando banco de dados...")
    with app.app_context():
        try:
            db.create_all()
            if not User.query.filter_by(username="admin").first():
                admin_user = User(username="admin", role="admin")
                admin_user.set_password("admin")
                db.session.add(admin_user)
                safe_commit()
                print("✅ Usuário admin criado (admin/admin)")
        except Exception as e:
            print(f"⚠️  Aviso na inicialização do BD: {e}")

    print(f"🌐 Servidor iniciando na porta {port}...")
    print("📍 O navegador abrirá automaticamente")
    print("⏹️  Para parar: Feche esta janela ou Ctrl+C")
    print("-" * 60)
    
    # Abre navegador
    open_browser(port)
    
    # Inicia servidor Flask
    try:
        app.run(
            host='127.0.0.1',
            port=port,
            debug=False,
            threaded=True,
            use_reloader=False
        )
    except Exception as e:
        print(f"❌ Erro no servidor: {e}")
        input("Pressione Enter para sair...")

if __name__ == "__main__":
    main()