"""
Aplicação principal Flask para o Sistema de Controle de Testes de Equipamentos.
Com abas separadas para novos equipamentos e equipamentos existentes.
"""
import os
import sys
from datetime import datetime, date, timezone, timedelta
from functools import wraps
from typing import Optional

from flask import (
    Flask,
    abort,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
    flash,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash

# -------------------------
# Configuração da aplicação
# -------------------------
app = Flask(__name__)

# Configura caminho do banco de dados para o executável
if getattr(sys, 'frozen', False):
    # Se está rodando como executável
    base_dir = os.path.dirname(sys.executable)
else:
    # Se está rodando como script
    base_dir = os.path.dirname(os.path.abspath(__file__))

db_path = os.path.join(base_dir, 'testes.db')
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "uma-chave-secreta-muito-segura-para-producao"

db = SQLAlchemy(app)

# -------------------------
# Flask-Login
# -------------------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Por favor, faça o login para acessar esta página."
login_manager.login_message_category = "info"


# -------------------------
# Helpers e utilitários
# -------------------------
def get_brasil_datetime():
    """Retorna o datetime atual no fuso horário do Brasil (America/Sao_Paulo)"""
    brasil_tz = timezone(timedelta(hours=-3))
    return datetime.now(brasil_tz)

def safe_commit() -> bool:
    """Tenta commitar a sessão; em caso de erro, faz rollback e retorna False."""
    try:
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        app.logger.exception("Erro no commit do banco de dados: %s", e)
        return False

def format_timedelta(delta: timedelta) -> str:
    """Formata um timedelta para algo legível como: '2d 3h 4m', '3h 12m' ou '45m'."""
    total_seconds = int(delta.total_seconds())
    days = total_seconds // 86400
    seconds_remaining = total_seconds % 86400
    hours = seconds_remaining // 3600
    minutes = (seconds_remaining % 3600) // 60

    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"

def admin_required(func):
    """Decorator simples para restringir acesso a administradores."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not getattr(current_user, "is_admin", False):
            abort(403)
        return func(*args, **kwargs)
    return wrapper


# -------------------------
# Models
# -------------------------
class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

class Equipamento(db.Model):
    __tablename__ = "equipamento"
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(100), nullable=False)
    modelo = db.Column(db.String(100), nullable=False)
    serial = db.Column(db.String(100), unique=True, nullable=False)
    status_atual = db.Column(db.String(50), default="Aguardando Teste")
    data_cadastro = db.Column(db.DateTime, default=get_brasil_datetime)
    testes = db.relationship(
        "Teste",
        backref="equipamento",
        lazy=True,
        order_by=lambda: Teste.data_teste.desc(),
        cascade="all, delete-orphan",
    )

class Teste(db.Model):
    __tablename__ = "teste"
    id = db.Column(db.Integer, primary_key=True)
    data_teste = db.Column(db.DateTime, default=get_brasil_datetime)
    status = db.Column(db.String(50), nullable=False)
    velocidade_teste = db.Column(db.String(50))
    sinal_dbm = db.Column(db.String(50))
    observacoes = db.Column(db.String(300))
    equipamento_id = db.Column(db.Integer, db.ForeignKey("equipamento.id"), nullable=False)


# -------------------------
# Util: filtros de busca
# -------------------------
def get_filtered_equipamentos_query(base_query):
    query_busca = request.args.get("q", "").strip()
    filtro_status = request.args.get("filtro_status", "").strip()
    filtro_dia = request.args.get("filtro_dia", "").strip()
    filtro_mes = request.args.get("filtro_mes", "").strip()

    if filtro_status:
        base_query = base_query.filter(Equipamento.status_atual == filtro_status)

    if filtro_dia or filtro_mes:
        base_query = base_query.join(Teste)
        try:
            if filtro_dia:
                dia = datetime.strptime(filtro_dia, "%Y-%m-%d").date()
                base_query = base_query.filter(db.func.date(Teste.data_teste) == dia)
            elif filtro_mes:
                mes_dt = datetime.strptime(filtro_mes, "%Y-%m")
                base_query = base_query.filter(
                    db.extract("year", Teste.data_teste) == mes_dt.year,
                    db.extract("month", Teste.data_teste) == mes_dt.month,
                )
        except (ValueError, TypeError):
            app.logger.warning("Filtro de data inválido: %s / %s", filtro_dia, filtro_mes)

    if query_busca:
        termo = f"%{query_busca}%"
        base_query = base_query.filter(
            or_(
                Equipamento.serial.ilike(termo),
                Equipamento.modelo.ilike(termo),
                Equipamento.tipo.ilike(termo),
            )
        )
    return base_query


# -------------------------
# Autoload de usuário
# -------------------------
@login_manager.user_loader
def load_user(user_id: str) -> Optional[User]:
    try:
        return User.query.get(int(user_id))
    except (ValueError, TypeError):
        return None


# -------------------------
# Rotas de autenticação
# -------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("index"))
        flash("Usuário ou senha inválidos.", "danger")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Você foi desconectado com sucesso.", "success")
    return redirect(url_for("login"))


# -------------------------
# Rotas principais
# -------------------------
@app.route("/")
@login_required
def index():
    """Página inicial com abas separadas."""
    todos_equipamentos = Equipamento.query.order_by(Equipamento.id.desc()).all()
    equipamentos_nao_testados = [eq for eq in todos_equipamentos if eq.status_atual == "Aguardando Teste"]
    equipamentos_testados = [eq for eq in todos_equipamentos if eq.testes]
    
    return render_template(
        "index.html",
        todos_equipamentos=todos_equipamentos,
        equipamentos_nao_testados=equipamentos_nao_testados,
        equipamentos_testados=equipamentos_testados
    )

@app.route("/add_equipamento", methods=["POST"])
@login_required
def add_equipamento():
    serial = (request.form.get("serial") or "").strip()
    tipo = (request.form.get("tipo") or "").strip()
    modelo = (request.form.get("modelo") or "").strip()

    if not serial or not tipo or not modelo:
        flash("Todos os campos (Tipo, Modelo, Serial) são obrigatórios.", "danger")
        return redirect(url_for("index"))

    existente = Equipamento.query.filter_by(serial=serial).first()
    
    if existente:
        existente.tipo = tipo
        existente.modelo = modelo
        existente.status_atual = "Aguardando Teste"
        
        if not safe_commit():
            flash("Erro ao atualizar equipamento. Tente novamente.", "danger")
        else:
            flash(f'Equipamento "{serial}" atualizado e pronto para novo teste!', "success")
    else:
        novo = Equipamento(serial=serial, tipo=tipo, modelo=modelo)
        db.session.add(novo)
        if not safe_commit():
            flash("Erro ao cadastrar equipamento. Tente novamente.", "danger")
        else:
            flash(f'Novo equipamento "{serial}" cadastrado com sucesso!', "success")
    
    return redirect(url_for("index"))

@app.route("/add_test/<int:equip_id>", methods=["POST"])
@login_required
def add_test(equip_id: int):
    equipamento = Equipamento.query.get_or_404(equip_id)
    status = request.form.get("status", "").strip()

    if not status:
        flash("O campo 'status' é obrigatório.", "danger")
        return redirect(url_for("index"))

    novo = Teste(
        status=status,
        velocidade_teste=request.form.get("velocidade_teste"),
        sinal_dbm=request.form.get("sinal_dbm"),
        observacoes=request.form.get("observacoes"),
        equipamento=equipamento
    )
    equipamento.status_atual = status
    db.session.add(novo)
    if not safe_commit():
        flash("Erro ao salvar teste. Tente novamente.", "danger")
    else:
        flash(f'Teste para o equipamento "{equipamento.serial}" salvo com sucesso!', "success")
    return redirect(url_for("index"))


# -------------------------
# Pesquisa, histórico e exclusões
# -------------------------
@app.route("/pesquisar")
@login_required
def pesquisar():
    base_query = Equipamento.query
    query_com_filtros = get_filtered_equipamentos_query(base_query)
    resultados = query_com_filtros.order_by(Equipamento.id.desc()).all()
    return render_template(
        "pesquisa.html",
        equipamentos=resultados,
        query_busca=request.args.get("q", ""),
        filtro_status=request.args.get("filtro_status", ""),
        filtro_dia=request.args.get("filtro_dia", ""),
        filtro_mes=request.args.get("filtro_mes", ""),
    )

@app.route("/historico/<int:equip_id>")
@login_required
def historico(equip_id: int):
    equipamento = Equipamento.query.get_or_404(equip_id)
    testes_ordenados = sorted(equipamento.testes, key=lambda t: t.data_teste)
    historico_processado, data_anterior = [], equipamento.data_cadastro or get_brasil_datetime()

    for teste in testes_ordenados:
        duracao = teste.data_teste - data_anterior
        historico_processado.append({"teste": teste, "tempo_em_campo": format_timedelta(duracao)})
        data_anterior = teste.data_teste

    historico_processado.reverse()
    return render_template("historico.html", equipamento=equipamento, historico=historico_processado)

@app.route("/delete/<int:id>", methods=["POST"])
@login_required
def delete(id: int):
    equipamento = Equipamento.query.get_or_404(id)
    db.session.delete(equipamento)
    if not safe_commit():
        flash("Erro ao deletar equipamento. Tente novamente.", "danger")
    else:
        flash("Equipamento e histórico foram deletados.", "success")
    return redirect(url_for("pesquisar"))


# -------------------------
# Administração de usuários
# -------------------------
@app.route("/admin/users")
@login_required
@admin_required
def manage_users():
    users = User.query.order_by(User.id).all()
    return render_template("admin_users.html", users=users)

@app.route("/admin/users/add", methods=["POST"])
@login_required
@admin_required
def add_user():
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password", "")
    role = request.form.get("role", "user")

    if not username or not password:
        flash("Nome de usuário e senha são obrigatórios.", "danger")
        return redirect(url_for("manage_users"))

    if User.query.filter_by(username=username).first():
        flash("Este nome de usuário já existe.", "warning")
        return redirect(url_for("manage_users"))

    novo = User(username=username, role=role)
    novo.set_password(password)
    db.session.add(novo)
    if not safe_commit():
        flash("Erro ao criar usuário. Tente novamente.", "danger")
    else:
        flash(f'Usuário "{username}" criado com sucesso.', "success")
    return redirect(url_for("manage_users"))

@app.route("/admin/users/delete/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id: int):
    user_to_delete = User.query.get_or_404(user_id)
    if user_to_delete.is_admin:
        flash("Não é possível deletar o usuário administrador.", "danger")
        return redirect(url_for("manage_users"))

    db.session.delete(user_to_delete)
    if not safe_commit():
        flash("Erro ao deletar usuário. Tente novamente.", "danger")
    else:
        flash("Usuário deletado com sucesso.", "success")
    return redirect(url_for("manage_users"))


# -------------------------
# Exportar PDF
# -------------------------
@app.route("/export/pesquisa/pdf")
@login_required
def export_pesquisa_pdf():
    """Versão simplificada sem PDF"""
    base_query = Equipamento.query
    query_com_filtros = get_filtered_equipamentos_query(base_query)
    resultados = query_com_filtros.order_by(Equipamento.id.desc()).all()
    
    # Gera HTML em vez de PDF
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Relatório de Equipamentos</title>
        <style>
            body {{ font-family: Arial; margin: 20px; }}
            h1 {{ color: #333; text-align: center; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
            th {{ background-color: #f5f5f5; }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>RELATÓRIO DE EQUIPAMENTOS</h1>
            <p>Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
            <p>Total de equipamentos: {len(resultados)}</p>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>Serial</th>
                    <th>Tipo</th>
                    <th>Modelo</th>
                    <th>Status</th>
                    <th>Data Cadastro</th>
                </tr>
            </thead>
            <tbody>
                {"".join([f'''
                <tr>
                    <td>{eq.serial}</td>
                    <td>{eq.tipo}</td>
                    <td>{eq.modelo}</td>
                    <td>{eq.status_atual}</td>
                    <td>{eq.data_cadastro.strftime('%d/%m/%Y')}</td>
                </tr>
                ''' for eq in resultados])}
            </tbody>
        </table>
        
        <div class="footer">
            <p>Relatório gerado pelo Sistema de Controle de Testes</p>
            <p><strong>Dica:</strong> Use Ctrl+P para imprimir ou salvar como PDF</p>
        </div>
    </body>
    </html>
    """
    
    response = make_response(html_content)
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    response.headers["Content-Disposition"] = f"attachment; filename=relatorio_equipamentos_{date.today()}.html"
    return response

@app.route("/historico/<int:equip_id>/export/pdf")
@login_required
def export_historico_pdf(equip_id: int):
    """Versão simplificada sem PDF"""
    equipamento = Equipamento.query.get_or_404(equip_id)
    testes_ordenados = sorted(equipamento.testes, key=lambda t: t.data_teste)
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Histórico - {equipamento.serial}</title>
        <style>
            body {{ font-family: Arial; margin: 20px; }}
            h1 {{ color: #333; }}
            .info {{ background: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
            th {{ background-color: #f5f5f5; }}
        </style>
    </head>
    <body>
        <h1>HISTÓRICO DE TESTES</h1>
        
        <div class="info">
            <h3>Equipamento: {equipamento.serial}</h3>
            <p><strong>Tipo:</strong> {equipamento.tipo}</p>
            <p><strong>Modelo:</strong> {equipamento.modelo}</p>
            <p><strong>Status Atual:</strong> {equipamento.status_atual}</p>
        </div>
        
        <h3>Testes Realizados ({len(testes_ordenados)})</h3>
        <table>
            <thead>
                <tr>
                    <th>Data</th>
                    <th>Status</th>
                    <th>Velocidade</th>
                    <th>Sinal</th>
                    <th>Observações</th>
                </tr>
            </thead>
            <tbody>
                {"".join([f'''
                <tr>
                    <td>{teste.data_teste.strftime('%d/%m/%Y %H:%M')}</td>
                    <td>{teste.status}</td>
                    <td>{teste.velocidade_teste or '-'}</td>
                    <td>{teste.sinal_dbm or '-'}</td>
                    <td>{teste.observacoes or '-'}</td>
                </tr>
                ''' for teste in reversed(testes_ordenados)])}
            </tbody>
        </table>
        
        <div style="margin-top: 30px; font-size: 12px; color: #666;">
            <p>Relatório gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
            <p><strong>Dica:</strong> Use Ctrl+P para imprimir ou salvar como PDF</p>
        </div>
    </body>
    </html>
    """
    
    response = make_response(html_content)
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    response.headers["Content-Disposition"] = f"attachment; filename=historico_{equipamento.serial}.html"
    return response


# -------------------------
# CLI helpers
# -------------------------
@app.cli.command("init-db")
def init_db_command():
    """Cria ou recria as tabelas do banco de dados."""
    db.create_all()
    print("✅ Banco de dados inicializado com sucesso.")

@app.cli.command("create-admin")
def create_admin_command():
    """Cria o usuário 'admin' inicial se ele não existir."""
    if User.query.filter_by(username="admin").first():
        print("ℹ️ Usuário 'admin' já existe.")
        return
    admin_user = User(username="admin", role="admin")
    admin_user.set_password("admin")
    db.session.add(admin_user)
    if not safe_commit():
        print("❌ Erro ao criar usuário administrador.")
    else:
        print("✅ Usuário 'admin' criado com a senha 'admin'.")


# -------------------------
# Error handlers
# -------------------------
@app.errorhandler(403)
def forbidden_error(error):
    return render_template("403.html"), 403

@app.errorhandler(404)
def not_found_error(error):
    return render_template("404.html"), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template("500.html"), 500
