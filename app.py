# -*- coding: utf-8 -*-
"""
Aplicação principal Flask para o Sistema de Controle de Testes de Equipamentos.
Versão final refatorada, consolidando todas as funcionalidades e correções.
"""
import os
import sys
import base64
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
from weasyprint import HTML
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

# Configura o caminho do banco de dados para funcionar tanto em script quanto em executável
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
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
def get_logo_base64():
    """Lê o arquivo de logo e o converte para Base64 para embutir no PDF.

    Returns:
        str: A representação em Base64 da imagem do logo, ou None se o arquivo não for encontrado.
    """
    try:
        logo_path = os.path.join(app.root_path, 'static', 'logo.png')
        with open(logo_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except FileNotFoundError:
        app.logger.warning("Ficheiro 'logo.png' não encontrado na pasta 'static'.")
        return None

def get_brasil_datetime():
    """Retorna o datetime atual no fuso horário de São Paulo (UTC-3).

    Returns:
        datetime: O objeto datetime com o fuso horário de São Paulo.
    """
    brasil_tz = timezone(timedelta(hours=-3))
    return datetime.now(brasil_tz)

def safe_commit() -> bool:
    """Tenta commitar a sessão; em caso de erro, faz rollback e retorna False.

    Returns:
        bool: True se o commit for bem-sucedido, False caso contrário.
    """
    try:
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        app.logger.exception("Erro no commit do banco de dados: %s", e)
        return False

def format_timedelta(delta: timedelta) -> str:
    """Formata um timedelta para algo legível como: '2d 3h 4m', '3h 12m' ou '45m'.

    Args:
        delta (timedelta): O objeto timedelta a ser formatado.

    Returns:
        str: A string formatada representando o timedelta.
    """
    if not isinstance(delta, timedelta):
        return "N/A"
    total_seconds = int(delta.total_seconds())
    days, seconds_remaining = divmod(total_seconds, 86400)
    hours, minutes_rem = divmod(seconds_remaining, 3600)
    minutes = minutes_rem // 60

    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"

def admin_required(func):
    """Decorator para restringir acesso a administradores (role='master').

    Args:
        func (function): A função a ser decorada.

    Returns:
        function: A função decorada que verifica as permissões de administrador.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return func(*args, **kwargs)
    return wrapper

def add_log(level: str, message: str):
    """Adiciona um novo registo de log ao banco de dados.

    Args:
        level (str): O nível do log (ex: 'INFO', 'WARNING', 'DANGER').
        message (str): A mensagem de log.
    """
    try:
        log_entry = Log(
            level=level,
            message=message,
            user_id=current_user.id if current_user.is_authenticated else None
        )
        db.session.add(log_entry)
        safe_commit()
    except Exception as e:
        app.logger.error(f"Falha ao registar log: {e}")

# -------------------------
# Models
# -------------------------
class User(UserMixin, db.Model):
    """Modelo de dados para usuários do sistema.

    Attributes:
        id (int): A chave primária do usuário.
        username (str): O nome de usuário, único.
        password_hash (str): O hash da senha do usuário.
        role (str): O papel do usuário (ex: 'suporte', 'master').
    """
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="suporte")
    testes = db.relationship('Teste', backref='tester', lazy=True)
    logs = db.relationship('Log', backref='user', lazy=True)

    @property
    def is_admin(self) -> bool:
        """Verifica se o usuário é um administrador."""
        return self.role == "master"

    def set_password(self, password: str) -> None:
        """Define a senha do usuário, gerando um hash.

        Args:
            password (str): A senha a ser definida.
        """
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verifica se a senha fornecida corresponde ao hash armazenado.

        Args:
            password (str): A senha a ser verificada.

        Returns:
            bool: True se a senha for válida, False caso contrário.
        """
        return check_password_hash(self.password_hash, password)

class Equipamento(db.Model):
    """Modelo de dados para equipamentos.

    Attributes:
        id (int): A chave primária do equipamento.
        tipo (str): O tipo de equipamento (ex: 'ONU', 'ROTEADOR').
        modelo (str): O modelo do equipamento.
        serial (str): O número de série ou MAC do equipamento, único.
        status_atual (str): O status atual do equipamento (ex: 'Aguardando Teste', 'Aprovado').
        data_cadastro (datetime): A data e hora do cadastro do equipamento.
    """
    __tablename__ = "equipamento"
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(100), nullable=False)
    modelo = db.Column(db.String(100), nullable=False)
    serial = db.Column(db.String(100), unique=True, nullable=False)
    status_atual = db.Column(db.String(50), default="Aguardando Teste")
    data_cadastro = db.Column(db.DateTime, default=get_brasil_datetime)
    testes = db.relationship("Teste", backref="equipamento", lazy=True, order_by=lambda: Teste.data_teste.desc(), cascade="all, delete-orphan")

class Teste(db.Model):
    """Modelo de dados para os testes realizados nos equipamentos.

    Attributes:
        id (int): A chave primária do teste.
        data_teste (datetime): A data e hora em que o teste foi realizado.
        status (str): O resultado do teste (ex: 'Aprovado', 'Reprovado').
        velocidade_teste (str): A velocidade medida no teste.
        sinal_dbm (str): O sinal em dBm medido no teste.
        observacoes (str): Observações adicionais sobre o teste.
        equipamento_id (int): A chave estrangeira para o equipamento testado.
        user_id (int): A chave estrangeira para o usuário que realizou o teste.
    """
    __tablename__ = "teste"
    id = db.Column(db.Integer, primary_key=True)
    data_teste = db.Column(db.DateTime, default=get_brasil_datetime)
    status = db.Column(db.String(50), nullable=False)
    velocidade_teste = db.Column(db.String(50))
    sinal_dbm = db.Column(db.String(50))
    observacoes = db.Column(db.String(300))
    equipamento_id = db.Column(db.Integer, db.ForeignKey("equipamento.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Log(db.Model):
    """Modelo de dados para logs do sistema.

    Attributes:
        id (int): A chave primária do log.
        timestamp (datetime): A data e hora do evento de log.
        level (str): O nível do log (ex: 'INFO', 'SUCCESS', 'WARNING', 'DANGER').
        message (str): A mensagem de log.
        user_id (int): A chave estrangeira para o usuário associado ao log.
    """
    __tablename__ = "log"
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=get_brasil_datetime, nullable=False)
    level = db.Column(db.String(20), nullable=False) # INFO, SUCCESS, WARNING, DANGER
    message = db.Column(db.String(500), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))


# -------------------------
# Autoload de usuário
# -------------------------
@login_manager.user_loader
def load_user(user_id: str) -> Optional[User]:
    """Carrega um usuário a partir do ID da sessão.

    Args:
        user_id (str): O ID do usuário a ser carregado.

    Returns:
        Optional[User]: O objeto do usuário, ou None se não for encontrado.
    """
    try:
        return User.query.get(int(user_id))
    except (ValueError, TypeError):
        return None

# -------------------------
# Rotas de autenticação
# -------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    """Rota para a página de login.

    Handles both GET and POST requests. On POST, validates user credentials.
    """
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        remember = True if request.form.get("remember") else False
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=remember)
            add_log("INFO", f"Utilizador '{user.username}' realizou login.")
            return redirect(url_for("index"))
        flash("Utilizador ou senha inválidos.", "danger")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    """Rota para fazer logout do usuário."""
    username = current_user.username
    logout_user()
    add_log("INFO", f"Utilizador '{username}' realizou logout.")
    flash("Você foi desconectado com sucesso.", "success")
    return redirect(url_for("login"))


# -------------------------
# Rotas principais
# -------------------------
@app.route("/")
@login_required
def index():
    """Rota para a página inicial, que exibe os equipamentos a serem testados e o histórico recente."""
    if current_user.role == 'agendamento':
        return redirect(url_for('pesquisar'))

    equipamentos_nao_testados = Equipamento.query.filter_by(status_atual="Aguardando Teste").order_by(Equipamento.id.desc()).all()
    equipamentos_testados = Equipamento.query.filter(Equipamento.status_atual != "Aguardando Teste").order_by(Equipamento.id.desc()).all()

    return render_template(
        "index.html",
        equipamentos_nao_testados=equipamentos_nao_testados,
        equipamentos_testados=equipamentos_testados
    )

@app.route("/add_equipamento", methods=["POST"])
@login_required
def add_equipamento():
    """Rota para adicionar um novo equipamento ou solicitar um re-teste para um existente."""
    if current_user.role == 'agendamento': abort(403)
    serial = (request.form.get("serial") or "").strip()

    if not serial:
        flash("O campo MAC é obrigatório.", "danger")
        return redirect(url_for("index"))

    existente = Equipamento.query.filter_by(serial=serial).first()
    if existente:
        existente.status_atual = "Aguardando Teste"
        if safe_commit():
            add_log("INFO", f"Solicitado re-teste para equipamento: {serial}.")
            flash(f'Equipamento "{serial}" pronto para re-teste na aba "Aguardando Teste".', "info")
        else:
            add_log("DANGER", f"Falha ao solicitar re-teste para: {serial}.")
            flash("Erro ao solicitar re-teste.", "danger")
    else:
        tipo = (request.form.get("tipo") or "").strip()
        modelo = (request.form.get("modelo") or "").strip()
        if not tipo or not modelo:
            flash("Para um equipamento novo, Tipo e Modelo também são obrigatórios.", "danger")
            return redirect(url_for("index"))

        novo = Equipamento(serial=serial, tipo=tipo, modelo=modelo)
        db.session.add(novo)
        if safe_commit():
            add_log("SUCCESS", f"Novo equipamento registado: {serial} ({tipo}/{modelo}).")
            flash(f'Novo equipamento "{serial}" registado! Ele está na aba "Aguardando Teste".', "success")
        else:
            add_log("DANGER", f"Falha ao registar novo equipamento: {serial}.")
            flash("Erro ao registar equipamento.", "danger")

    return redirect(url_for("index"))

@app.route("/add_test/<int:equip_id>", methods=["POST"])
@login_required
def add_test(equip_id: int):
    """Rota para adicionar o resultado de um teste a um equipamento.

    Args:
        equip_id (int): O ID do equipamento a ser testado.
    """
    if current_user.role == 'agendamento': abort(403)
    equipamento = Equipamento.query.get_or_404(equip_id)
    status = request.form.get("status", "").strip()

    if not status:
        flash("O campo 'Resultado' é obrigatório.", "danger")
        return redirect(url_for("index"))

    novo = Teste(
        status=status,
        velocidade_teste=request.form.get("velocidade_teste"),
        sinal_dbm=request.form.get("sinal_dbm"),
        observacoes=request.form.get("observacoes"),
        equipamento=equipamento,
        user_id=current_user.id
    )
    equipamento.status_atual = status
    db.session.add(novo)
    if safe_commit():
        add_log("SUCCESS", f"Teste '{status}' registado para equipamento: {equipamento.serial}.")
        flash(f'Teste para "{equipamento.serial}" salvo com sucesso!', "success")
    else:
        add_log("DANGER", f"Falha ao salvar teste para: {equipamento.serial}.")
        flash("Erro ao salvar teste.", "danger")
    return redirect(url_for("index"))


# -------------------------
# Pesquisa, histórico e exclusões
# -------------------------
def get_filtered_equipamentos_query(base_query):
    """Constrói uma query de equipamentos com base nos filtros da requisição.

    Args:
        base_query: A query base de equipamentos a ser filtrada.

    Returns:
        A query de equipamentos com os filtros aplicados.
    """
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
                base_query = base_query.filter(db.extract("year", Teste.data_teste) == mes_dt.year, db.extract("month", Teste.data_teste) == mes_dt.month)
        except (ValueError, TypeError):
            app.logger.warning("Filtro de data inválido: %s / %s", filtro_dia, filtro_mes)
    if query_busca:
        termo = f"%{query_busca}%"
        base_query = base_query.filter(or_(Equipamento.serial.ilike(termo), Equipamento.modelo.ilike(termo), Equipamento.tipo.ilike(termo)))
    return base_query

@app.route("/pesquisar")
@login_required
def pesquisar():
    """Rota para a página de pesquisa de equipamentos, com filtros."""
    base_query = Equipamento.query
    query_com_filtros = get_filtered_equipamentos_query(base_query)
    resultados = query_com_filtros.order_by(Equipamento.id.desc()).all()
    if current_user.role == 'agendamento':
        return render_template("agendamento_index.html", equipamentos=resultados)
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
    """Rota para a página de histórico de testes de um equipamento específico.

    Args:
        equip_id (int): O ID do equipamento a ser visualizado.
    """
    equipamento = Equipamento.query.get_or_404(equip_id)
    return render_template("historico.html", equipamento=equipamento, historico=equipamento.testes)

@app.route("/delete/<int:id>", methods=["POST"])
@login_required
def delete(id: int):
    """Rota para apagar um equipamento e todo o seu histórico.

    Args:
        id (int): O ID do equipamento a ser apagado.
    """
    if current_user.role == 'agendamento': abort(403)
    equipamento = Equipamento.query.get_or_404(id)
    serial = equipamento.serial
    db.session.delete(equipamento)
    if safe_commit():
        add_log("WARNING", f"Equipamento '{serial}' e todo o seu histórico foram apagados.")
        flash("Equipamento e histórico foram apagados.", "success")
    else:
        add_log("DANGER", f"Falha ao apagar equipamento '{serial}'.")
        flash("Erro ao apagar equipamento.", "danger")
    return redirect(url_for("pesquisar"))


# -------------------------
# Administração
# -------------------------
@app.route("/admin/users")
@login_required
@admin_required
def manage_users():
    """Rota para a página de gerenciamento de usuários (apenas para administradores)."""
    users = User.query.order_by(User.id).all()
    return render_template("admin_users.html", users=users)

@app.route("/admin/users/add", methods=["POST"])
@login_required
@admin_required
def add_user():
    """Rota para adicionar um novo usuário (apenas para administradores)."""
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password", "")
    role = request.form.get("role", "suporte")
    if not username or not password:
        flash("Nome de utilizador e senha são obrigatórios.", "danger")
        return redirect(url_for("manage_users"))
    if User.query.filter_by(username=username).first():
        flash("Este nome de utilizador já existe.", "warning")
        return redirect(url_for("manage_users"))
    novo = User(username=username, role=role)
    novo.set_password(password)
    db.session.add(novo)
    if safe_commit():
        add_log("SUCCESS", f"Novo utilizador '{username}' (role: {role}) foi criado.")
        flash(f'Utilizador "{username}" criado com sucesso.', "success")
    else:
        add_log("DANGER", f"Falha ao criar utilizador '{username}'.")
        flash("Erro ao criar utilizador.", "danger")
    return redirect(url_for("manage_users"))

@app.route("/admin/users/delete/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id: int):
    """Rota para apagar um usuário (apenas para administradores).

    Args:
        user_id (int): O ID do usuário a ser apagado.
    """
    user_to_delete = User.query.get_or_404(user_id)
    username = user_to_delete.username
    if user_to_delete.role == 'master':
        flash("Não é possível apagar o utilizador master.", "danger")
        return redirect(url_for("manage_users"))
    db.session.delete(user_to_delete)
    if safe_commit():
        add_log("WARNING", f"Utilizador '{username}' foi apagado.")
        flash("Utilizador apagado com sucesso.", "success")
    else:
        add_log("DANGER", f"Falha ao apagar utilizador '{username}'.")
        flash("Erro ao apagar utilizador.", "danger")
    return redirect(url_for("manage_users"))

@app.route('/admin/users/reset_password/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def reset_user_password(user_id: int):
    """Rota para redefinir a senha de um usuário (apenas para administradores).

    Args:
        user_id (int): O ID do usuário a ter a senha redefinida.
    """
    user_to_reset = User.query.get_or_404(user_id)
    username = user_to_reset.username
    new_password = request.form.get('new_password')
    if user_to_reset.role == 'master':
        flash('Não é possível resetar a senha do utilizador master por aqui.', 'danger')
        return redirect(url_for('manage_users'))
    if not new_password:
        flash('A nova senha não pode estar em branco.', 'danger')
        return redirect(url_for('manage_users'))
    user_to_reset.set_password(new_password)
    if safe_commit():
        add_log("WARNING", f"Senha do utilizador '{username}' foi resetada.")
        flash(f'Senha do utilizador "{username}" foi resetada com sucesso.', 'success')
    else:
        add_log("DANGER", f"Falha ao resetar senha do utilizador '{username}'.")
        flash('Erro ao resetar a senha.', 'danger')
    return redirect(url_for('manage_users'))

@app.route('/admin/logs')
@login_required
@admin_required
def view_logs():
    """Rota para a página de visualização de logs do sistema (apenas para administradores)."""
    page = request.args.get('page', 1, type=int)
    logs = Log.query.order_by(Log.timestamp.desc()).paginate(page=page, per_page=50)
    return render_template('admin_logs.html', logs=logs)


# -------------------------
# Exportar PDF
# -------------------------
@app.route("/export/pesquisa/pdf")
@login_required
def export_pesquisa_pdf():
    """Rota para exportar os resultados da pesquisa atual para um arquivo PDF."""
    base_query = Equipamento.query; query_com_filtros = get_filtered_equipamentos_query(base_query); resultados = query_com_filtros.order_by(Equipamento.id.desc()).all()
    logo_b64 = get_logo_base64()
    html = render_template("relatorio_pesquisa_pdf.html", equipamentos=resultados, now=get_brasil_datetime(), logo_base64=logo_b64)
    pdf = HTML(string=html).write_pdf(); response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"; response.headers["Content-Disposition"] = f'inline; filename=relatorio_pesquisa_{date.today()}.pdf'
    return response

@app.route("/historico/<int:equip_id>/export/pdf")
@login_required
def export_historico_pdf(equip_id: int):
    """Rota para exportar o histórico de um equipamento para um arquivo PDF.

    Args:
        equip_id (int): O ID do equipamento a ter seu histórico exportado.
    """
    equipamento = Equipamento.query.get_or_404(equip_id)
    logo_b64 = get_logo_base64()
    html = render_template("relatorio_historico_pdf.html", equipamento=equipamento, historico=equipamento.testes, now=get_brasil_datetime(), logo_base64=logo_b64)
    pdf = HTML(string=html).write_pdf(); response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"; response.headers["Content-Disposition"] = f'inline; filename=historico_{equipamento.serial}.pdf'
    return response


# -------------------------
# CLI helpers
# -------------------------
@app.cli.command("init-db")
def init_db_command():
    """Comando CLI para inicializar o banco de dados."""
    db.create_all()
    print("✅ Banco de dados inicializado com sucesso.")

@app.cli.command("create-master")
def create_master_command():
    """Comando CLI para criar um usuário 'master' com uma senha padrão."""
    if User.query.filter_by(username="master").first(): print("ℹ️ Utilizador 'master' já existe."); return
    master_user = User(username="master", role="master")
    master_user.set_password("105391@Lu")
    db.session.add(master_user)
    if safe_commit(): print("✅ Utilizador 'master' criado com a senha segura.")
    else: print("❌ Erro ao criar utilizador master.")


# -------------------------
# Error handlers
# -------------------------
@app.errorhandler(403)
def forbidden_error(error):
    """Manipulador de erro para o código de status 403 (Proibido)."""
    return render_template("403.html"), 403

@app.errorhandler(404)
def not_found_error(error):
    """Manipulador de erro para o código de status 404 (Não Encontrado)."""
    return render_template("404.html"), 404

@app.errorhandler(500)
def internal_error(error):
    """Manipulador de erro para o código de status 500 (Erro Interno do Servidor)."""
    db.session.rollback()
    return render_template("500.html"), 500

if __name__ == "__main__":
    app.run(debug=True)
