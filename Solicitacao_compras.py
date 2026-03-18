import os
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


# =========================
# APP + PATHS
# =========================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")

UPLOADS_DIR = os.path.join(STATIC_DIR, "uploads")
COVERS_DIR = os.path.join(UPLOADS_DIR, "covers")
PDFS_DIR = os.path.join(UPLOADS_DIR, "pdfs")

for d in [INSTANCE_DIR, UPLOADS_DIR, COVERS_DIR, PDFS_DIR]:
    os.makedirs(d, exist_ok=True)

DB_PATH = os.path.join(INSTANCE_DIR, "app.db")
DB_URI = "sqlite:///" + DB_PATH.replace("\\", "/")


app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=STATIC_DIR)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET", "dev_secret_change_me")
app.config["SQLALCHEMY_DATABASE_URI"] = DB_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# =========================
# MODELS
# =========================
class AdminUser(db.Model):
    __tablename__ = "admin_users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)

    sku = db.Column(db.String(80), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    price_text = db.Column(db.String(80), nullable=False, default="Sob consulta")

    short = db.Column(db.Text, nullable=True)
    description = db.Column(db.Text, nullable=True)

    image_path = db.Column(db.String(400), nullable=True)  # uploads/covers/...
    file_path = db.Column(db.String(400), nullable=True)   # uploads/pdfs/...

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class QuoteLog(db.Model):
    __tablename__ = "quote_logs"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    product_id = db.Column(db.Integer, nullable=True)
    product_name = db.Column(db.String(255), nullable=True)
    product_sku = db.Column(db.String(80), nullable=True)

    nome = db.Column(db.String(120), nullable=False)
    empresa = db.Column(db.String(160), nullable=False)
    cnpjcpf = db.Column(db.String(60), nullable=False)
    email = db.Column(db.String(160), nullable=False)
    telefone = db.Column(db.String(60), nullable=False)
    mensagem = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(30), nullable=False, default="enviado")  # enviado | erro
    error = db.Column(db.Text, nullable=True)


# =========================
# HELPERS
# =========================
ALLOWED_COVER_EXT = {"jpg", "jpeg", "png", "webp"}
ALLOWED_PDF_EXT = {"pdf"}

def ext_of(filename: str) -> str:
    filename = filename.lower().strip()
    return filename.rsplit(".", 1)[-1] if "." in filename else ""

def safe_filename(filename: str) -> str:
    filename = secure_filename(filename)
    return filename or "file"

def normalize_q(s: str) -> str:
    return (s or "").strip()

def admin_required():
    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))
    return None

def create_admin_if_missing():
    user = os.getenv("ADMIN_USER", "admin").strip()
    pw = os.getenv("ADMIN_PASS", "admin123").strip()

    existing = AdminUser.query.filter_by(username=user).first()
    if existing:
        return

    au = AdminUser(username=user, password_hash=generate_password_hash(pw))
    db.session.add(au)
    db.session.commit()
    print(f"[OK] Admin criado: {user} (senha do .env)")


# ✅ ALTERAÇÃO SOLICITADA:
# - Subject no formato: "Orçamento - NOME (SKU XXX)"
# - From com nome exibido: "FSantosServiços - orçamento. <email@...>"
# - Reply-To = email do cliente
# - Suporte a TLS/SSL via env
def send_email_quote(subject: str, body: str, reply_to: str | None = None) -> (bool, str | None):
    host = os.getenv("SMTP_HOST", "").strip()
    port_raw = os.getenv("SMTP_PORT", "25").strip()
    user = os.getenv("SMTP_USER", "").strip()
    pw = os.getenv("SMTP_PASS", "").strip()

    from_addr = os.getenv("SMTP_FROM", "").strip()
    to_addr = os.getenv("SMTP_TO", "").strip()

    from_name = os.getenv("SMTP_FROM_NAME", "FSantosServiços - orçamento.").strip()

    tls = os.getenv("SMTP_TLS", "false").strip().lower() in ("1", "true", "yes", "sim")
    ssl = os.getenv("SMTP_SSL", "false").strip().lower() in ("1", "true", "yes", "sim")

    if not host or not from_addr or not to_addr:
        missing = []
        if not host: missing.append("SMTP_HOST")
        if not from_addr: missing.append("SMTP_FROM")
        if not to_addr: missing.append("SMTP_TO")
        return False, "SMTP não configurado: faltando " + ", ".join(missing)

    try:
        port = int(port_raw or "25")
    except Exception:
        return False, f"SMTP_PORT inválido: {port_raw}"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_addr}>"
    msg["To"] = to_addr
    if reply_to:
        msg["Reply-To"] = reply_to

    msg.set_content(body)

    try:
        if ssl:
            with smtplib.SMTP_SSL(host, port, timeout=35) as s:
                s.ehlo()
                if user:
                    s.login(user, pw)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=35) as s:
                s.ehlo()
                if tls:
                    s.starttls()
                    s.ehlo()
                if user:
                    s.login(user, pw)
                s.send_message(msg)

        return True, None
    except Exception as e:
        return False, str(e)


# =========================
# INIT
# =========================
def init_all():
    with app.app_context():
        db.create_all()
        create_admin_if_missing()


# =========================
# ROUTES - VITRINE
# =========================
@app.get("/")
def home():
    q = normalize_q(request.args.get("q", ""))

    query = Product.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Product.sku.ilike(like),
                Product.name.ilike(like),
                Product.short.ilike(like),
                Product.description.ilike(like),
            )
        )

    products = query.order_by(Product.created_at.desc()).all()

    return render_template(
        "index.html",
        products=products,
        q=q,
        year=datetime.now().year,
        title="FSantos Serviços"
    )


@app.post("/orcamento")
def orcamento():
    product_id = (request.form.get("product_id") or "").strip()
    nome = (request.form.get("nome") or "").strip()
    empresa = (request.form.get("empresa") or "").strip()
    cnpjcpf = (request.form.get("cnpjcpf") or "").strip()
    email = (request.form.get("email") or "").strip()
    telefone = (request.form.get("telefone") or "").strip()
    mensagem = (request.form.get("mensagem") or "").strip()

    if not (nome and empresa and cnpjcpf and email and telefone):
        flash("Preencha todos os campos obrigatórios.", "danger")
        return redirect(url_for("home"))

    product = None
    if product_id.isdigit():
        product = Product.query.get(int(product_id))

    # ✅ ASSUNTO NO FORMATO DA 2ª IMAGEM
    if product:
        subject = f"Orçamento - {product.name} (SKU {product.sku})"
    else:
        subject = "Orçamento - Solicitação"

    body = []
    body.append("=== SOLICITAÇÃO DE ORÇAMENTO ===")
    if product:
        body.append(f"Produto: {product.name}")
        body.append(f"SKU: {product.sku}")
        body.append(f"Preço: {product.price_text}")
    body.append("")
    body.append(f"Nome: {nome}")
    body.append(f"Empresa/Cliente: {empresa}")
    body.append(f"CNPJ/CPF: {cnpjcpf}")
    body.append(f"E-mail: {email}")
    body.append(f"Telefone: {telefone}")
    if mensagem:
        body.append("")
        body.append("Mensagem:")
        body.append(mensagem)

    # ✅ Reply-To = email do cliente (quando clicar responder vai pra ele)
    sent, err = send_email_quote(subject, "\n".join(body), reply_to=email)

    try:
        log = QuoteLog(
            product_id=(product.id if product else None),
            product_name=(product.name if product else None),
            product_sku=(product.sku if product else None),
            nome=nome, empresa=empresa, cnpjcpf=cnpjcpf,
            email=email, telefone=telefone,
            mensagem=mensagem or None,
            status=("enviado" if sent else "erro"),
            error=(err if err else None)
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass

    if err:
        flash(f"Orçamento registrado, mas NÃO foi enviado por e-mail: {err}", "warning")
    else:
        flash("Orçamento enviado com sucesso!", "success")

    return redirect(url_for("home"))


# =========================
# ROUTES - ADMIN AUTH
# =========================
@app.get("/admin/login")
def admin_login():
    return render_template("admin_login.html", year=datetime.now().year, title="Admin")

@app.post("/admin/login")
def admin_login_post():
    username = (request.form.get("username") or "").strip()
    password = (request.form.get("password") or "").strip()

    u = AdminUser.query.filter_by(username=username).first()
    if not u or not check_password_hash(u.password_hash, password):
        flash("Usuário ou senha inválidos.", "danger")
        return redirect(url_for("admin_login"))

    session["admin_logged"] = True
    session["admin_user"] = u.username
    return redirect(url_for("admin_dashboard"))

@app.get("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("home"))


# =========================
# ROUTES - ADMIN DASHBOARD / LOGS
# =========================
@app.get("/admin")
def admin_root():
    r = admin_required()
    if r: return r
    return redirect(url_for("admin_dashboard"))

@app.get("/admin/dashboard")
def admin_dashboard():
    r = admin_required()
    if r: return r

    total_produtos = Product.query.count()
    total_orcamentos = QuoteLog.query.count()
    total_hoje = QuoteLog.query.filter(
        QuoteLog.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    ).count()

    since = datetime.utcnow() - timedelta(days=13)
    rows = (
        db.session.query(db.func.date(QuoteLog.created_at).label("d"), db.func.count(QuoteLog.id).label("c"))
        .filter(QuoteLog.created_at >= since)
        .group_by(db.func.date(QuoteLog.created_at))
        .order_by(db.func.date(QuoteLog.created_at))
        .all()
    )

    by_day = {str(r.d): int(r.c) for r in rows}
    labels, data = [], []
    for i in range(14):
        day = (since + timedelta(days=i)).date()
        key = str(day)
        labels.append(day.strftime("%d/%m"))
        data.append(by_day.get(key, 0))

    last_logs = QuoteLog.query.order_by(QuoteLog.created_at.desc()).limit(10).all()

    return render_template(
        "admin_dashboard.html",
        year=datetime.now().year,
        total_produtos=total_produtos,
        total_orcamentos=total_orcamentos,
        total_hoje=total_hoje,
        chart_labels=labels,
        chart_data=data,
        last_logs=last_logs,
        title="Admin — Dashboard"
    )

@app.get("/admin/orcamentos")
def admin_orcamentos():
    r = admin_required()
    if r: return r

    q = normalize_q(request.args.get("q", ""))
    query = QuoteLog.query

    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                QuoteLog.nome.ilike(like),
                QuoteLog.empresa.ilike(like),
                QuoteLog.cnpjcpf.ilike(like),
                QuoteLog.email.ilike(like),
                QuoteLog.telefone.ilike(like),
                QuoteLog.product_name.ilike(like),
                QuoteLog.product_sku.ilike(like),
                QuoteLog.status.ilike(like),
            )
        )

    logs = query.order_by(QuoteLog.created_at.desc()).limit(600).all()

    return render_template(
        "admin_orcamentos.html",
        year=datetime.now().year,
        logs=logs,
        q=q,
        title="Admin — Orçamentos"
    )


# =========================
# ROUTES - ADMIN PRODUCTS CRUD
# =========================
@app.get("/admin/produtos")
def admin_products():
    r = admin_required()
    if r: return r

    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template(
        "admin_products.html",
        year=datetime.now().year,
        products=products,
        title="Admin — Produtos"
    )

@app.post("/admin/produtos/novo")
def admin_products_new():
    r = admin_required()
    if r: return r

    sku = (request.form.get("sku") or "").strip()
    name = (request.form.get("name") or "").strip()
    price_text = (request.form.get("price_text") or "Sob consulta").strip()
    short = (request.form.get("short") or "").strip() or None
    description = (request.form.get("description") or "").strip() or None

    if not sku or not name:
        flash("SKU e Nome são obrigatórios.", "danger")
        return redirect(url_for("admin_products"))

    p = Product(sku=sku, name=name, price_text=price_text, short=short, description=description)
    db.session.add(p)
    db.session.commit()

    cover_file = request.files.get("cover_file")
    if cover_file and cover_file.filename:
        e = ext_of(cover_file.filename)
        if e not in ALLOWED_COVER_EXT:
            flash("Capa inválida. Use JPG/PNG/WEBP.", "warning")
        else:
            fn = safe_filename(f"cover_{p.id}_{int(datetime.utcnow().timestamp())}.{e}")
            cover_file.save(os.path.join(COVERS_DIR, fn))
            p.image_path = f"uploads/covers/{fn}"
            p.updated_at = datetime.utcnow()
            db.session.commit()

    pdf_file = request.files.get("pdf_file")
    if pdf_file and pdf_file.filename:
        e = ext_of(pdf_file.filename)
        if e not in ALLOWED_PDF_EXT:
            flash("PDF inválido.", "warning")
        else:
            fn = safe_filename(f"pdf_{p.id}_{int(datetime.utcnow().timestamp())}.{e}")
            pdf_file.save(os.path.join(PDFS_DIR, fn))
            p.file_path = f"uploads/pdfs/{fn}"
            p.updated_at = datetime.utcnow()
            db.session.commit()

    flash("Produto cadastrado com sucesso!", "success")
    return redirect(url_for("admin_products"))


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    import sys

    if "--init" in sys.argv:
        with app.app_context():
            db.create_all()
            create_admin_if_missing()
        print("[OK] Banco inicializado e admin garantido.")
        sys.exit(0)

    init_all()
    print(">>> SERVIDOR INICIADO: Solicitacao_compras.py <<<")
    print(">>> PASTA DO APP:", BASE_DIR)
    app.run(host="127.0.0.1", port=5000, debug=True)
