from flask import Flask, render_template, request, flash, redirect, url_for, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv
from collections import Counter
from datetime import datetime, timedelta
import pandas as pd
from fpdf import FPDF
import random
import os
import io
import re
from sqlalchemy import func

# --- IMPORT DA IA ---
from google import genai

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'chave-padrao-insegura')

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static/uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

csrf = CSRFProtect(app)
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- CONFIGURAÇÃO DA IA ---
CHAVE_API = "SUA_CHAVE_AQUI_AIza..." 

try:
    client = genai.Client(api_key=CHAVE_API)
except Exception as e:
    print(f"Aviso: IA não configurada. {e}")
    client = None

# --- MODELOS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    telefone = db.Column(db.String(20))
    senha = db.Column(db.String(100))
    foto_perfil = db.Column(db.String(120), default='default.png')
    is_admin = db.Column(db.Boolean, default=False)
    jogos = db.relationship('JogoSalvo', backref='dono', lazy=True)

class JogoSalvo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numeros = db.Column(db.String(100))
    tipo = db.Column(db.String(50))
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class ResultadoLotofacil(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    concurso = db.Column(db.Integer, unique=True, nullable=False)
    data_sorteio = db.Column(db.String(20))
    dezenas = db.Column(db.String(100))

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- ESTATÍSTICAS ---
def obter_estatisticas(limite=10):
    query = ResultadoLotofacil.query.order_by(ResultadoLotofacil.concurso.desc())
    if limite > 0: resultados_db = query.limit(limite).all()
    else: resultados_db = query.all()
    todos_numeros = []
    if resultados_db:
        for res in resultados_db:
            nums = [int(n) for n in re.findall(r'\d+', res.dezenas)]
            todos_numeros.extend(nums)
    top_10 = Counter(todos_numeros).most_common(10)
    stats_ordenado = sorted(top_10, key=lambda x: x[0])
    return stats_ordenado

# --- ROTAS ---
@app.route('/')
def index():
    filtro = request.args.get('filtro', default=10, type=int)
    stats = obter_estatisticas(filtro)
    ultimo_concurso_db = ResultadoLotofacil.query.order_by(ResultadoLotofacil.concurso.desc()).first()
    chart_labels = [f"{x[0]:02d}" for x in stats]
    chart_data = [x[1] for x in stats]
    return render_template('index.html', estatisticas=stats, filtro_atual=filtro, ultimo_concurso_db=ultimo_concurso_db, chart_labels=chart_labels, chart_data=chart_data)

@app.route('/api/estatisticas/<int:limite>')
def api_estatisticas(limite):
    stats = obter_estatisticas(limite)
    labels = [f"{x[0]:02d}" for x in stats]
    values = [x[1] for x in stats]
    html_lista = ""
    for num, qtd in stats:
        html_lista += f'<div class="border rounded-3 px-2 py-1 text-center bg-light" style="min-width: 50px;"><span class="d-block fw-bold fs-6 text-danger">{num:02d}</span><span class="small text-muted">{qtd}x</span></div>'
    return jsonify({'labels': labels, 'data': values, 'html': html_lista})

# --- GERAÇÃO PURA (MODIFICADA: TIPO LIMPO) ---
@app.route('/gerar-pura', methods=['POST'])
def gerar_pura():
    ultimo_concurso_db = ResultadoLotofacil.query.order_by(ResultadoLotofacil.concurso.desc()).first()
    
    ultimos_10 = ResultadoLotofacil.query.order_by(ResultadoLotofacil.concurso.desc()).limit(10).all()
    if not ultimos_10:
        flash("Preciso de pelo menos 10 resultados cadastrados no Admin para calcular a Estatística Pura.", "warning")
        return redirect(url_for('index'))

    todos_numeros = []
    ultimo_resultado_nums = set()
    if ultimos_10:
        ultimo_resultado_nums = set(int(n) for n in re.findall(r'\d+', ultimos_10[0].dezenas))

    for res in ultimos_10:
        nums = [int(n) for n in re.findall(r'\d+', res.dezenas)]
        todos_numeros.extend(nums)
    
    contagem = Counter(todos_numeros)
    lista_analise = []
    for n in range(1, 26):
        freq = contagem[n]
        no_ultimo = 1 if n in ultimo_resultado_nums else 0
        lista_analise.append({'num': n, 'freq': freq, 'hot': no_ultimo})

    ranking = sorted(lista_analise, key=lambda x: (x['freq'], x['hot'], x['num']), reverse=True)
    fixas_obj = ranking[:7]
    reservas_obj = ranking[7:]
    fixas = sorted([x['num'] for x in fixas_obj])
    reservas = [x['num'] for x in reservas_obj]

    jogos = []
    # Jogo 1
    comp1 = reservas[:8]
    j1_nums = sorted(fixas + comp1)
    # AQUI: Criamos 'tipo' (com emoji) e 'tipo_limpo' (sem emoji)
    jogos.append({
        'tipo': 'Pura - Lógica (Top Reservas) 🧠', 
        'tipo_limpo': 'Pura - Lógica',
        'numeros': j1_nums, 
        'numeros_str': ", ".join([f"{n:02d}" for n in j1_nums]), 
        'zap': f"Pura Lógica: {j1_nums}"
    })
    # Jogo 2
    comp2 = reservas[:5] + reservas[-3:]
    j2_nums = sorted(fixas + comp2)
    jogos.append({
        'tipo': 'Pura - Equilíbrio (C/ Zebras) ⚖️', 
        'tipo_limpo': 'Pura - Equilíbrio',
        'numeros': j2_nums, 
        'numeros_str': ", ".join([f"{n:02d}" for n in j2_nums]), 
        'zap': f"Pura Equilíbrio: {j2_nums}"
    })
    # Jogo 3
    comp3 = reservas[5:13] 
    j3_nums = sorted(fixas + comp3)
    jogos.append({
        'tipo': 'Pura - Intermediária (Meio Tabela) 🎯', 
        'tipo_limpo': 'Pura - Intermediária',
        'numeros': j3_nums, 
        'numeros_str': ", ".join([f"{n:02d}" for n in j3_nums]), 
        'zap': f"Pura Meio: {j3_nums}"
    })

    stats = obter_estatisticas(10)
    chart_labels = [f"{x[0]:02d}" for x in stats]
    chart_data = [x[1] for x in stats]

    flash("Estratégia Pura calculada com sucesso! (3 Jogos)", "success")
    return render_template('index.html', jogos=jogos, estatisticas=stats, filtro_atual=10, chart_labels=chart_labels, chart_data=chart_data, pura_fixas=fixas, ultimo_concurso_db=ultimo_concurso_db)

# --- GERAÇÃO PADRÃO (MODIFICADA: TIPO LIMPO) ---
@app.route('/gerar-ouro', methods=['POST'])
def gerar_ouro():
    ultimo_concurso_db = ResultadoLotofacil.query.order_by(ResultadoLotofacil.concurso.desc()).first()

    ultimo = [int(n) for n in request.form.getlist('numeros')]
    fixos = [int(n) for n in request.form.getlist('fixos')]
    filtro = request.form.get('filtro_hidden', default=10, type=int)
    qtd_jogos = int(request.form.get('qtd_jogos', 4))
    stats = obter_estatisticas(filtro)
    chart_labels = [f"{x[0]:02d}" for x in stats]
    chart_data = [x[1] for x in stats]
    
    if len(ultimo) != 15 or len(fixos) < 1 or len(fixos) > 14:
        flash("Verifique os números marcados na aba Estratégia.", "warning")
        return redirect(url_for('index'))

    todos, set_fixos = set(range(1, 26)), set(fixos)
    disponiveis = list(todos - set_fixos)
    jogos = []
    for i in range(qtd_jogos):
        try:
            restantes = 15 - len(set_fixos)
            if restantes > 0:
                comp = random.sample(disponiveis, restantes)
                final = sorted(list(set_fixos) + comp)
            else: final = sorted(list(set_fixos))
            nums_fmt = ", ".join([f"{n:02d}" for n in final])
            letra = chr(65 + i) if i < 26 else f"#{i+1}"
            jogos.append({
                'tipo': f'Estratégia Padrão {letra}', 
                'tipo_limpo': f'Estratégia Padrão {letra}', # Sem emoji mesmo
                'numeros': final, 
                'numeros_str': nums_fmt, 
                'zap': f"Jogo {letra}: {nums_fmt}"
            })
        except: pass

    flash(f"{len(jogos)} Jogos gerados com sucesso!", "success")
    return render_template('index.html', jogos=jogos, selecionados=ultimo, fixos_selecionados=fixos, estatisticas=stats, filtro_atual=filtro, chart_labels=chart_labels, chart_data=chart_data, ultimo_concurso_db=ultimo_concurso_db)

# --- MÉTODO 25 DEZENAS (MODIFICADA: TIPO LIMPO) ---
@app.route('/gerar-metodo-25', methods=['POST'])
def gerar_metodo_25():
    ultimo_concurso_db = ResultadoLotofacil.query.order_by(ResultadoLotofacil.concurso.desc()).first()

    ultimo_str = request.form.get('ultimo_resultado_25', '') 
    fixas_sorteadas = [int(n) for n in request.form.getlist('fixas_sorteadas')] 
    fixas_ausentes = [int(n) for n in request.form.getlist('fixas_ausentes')]   
    
    if not ultimo_str:
        flash("Primeiro preencha o Último Resultado na aba Método 25.", "danger"); return redirect(url_for('index'))

    sorteadas = set(int(n.strip()) for n in ultimo_str.split(',') if n.strip().isdigit())
    todas = set(range(1, 26))
    ausentes = todas - sorteadas

    if len(sorteadas) != 15: flash("O último resultado precisa ter 15 números.", "warning"); return redirect(url_for('index'))
    if len(fixas_sorteadas) != 3: flash("Você precisa escolher exatamente 3 Fixas das Sorteadas.", "warning"); return redirect(url_for('index'))
    if len(fixas_ausentes) != 2: flash("Você precisa escolher exatamente 2 Fixas das Ausentes.", "warning"); return redirect(url_for('index'))
    
    resto_sorteadas = list(sorteadas - set(fixas_sorteadas)); random.shuffle(resto_sorteadas)
    g1_sort = resto_sorteadas[:6]; g2_sort = resto_sorteadas[6:]
    resto_ausentes = list(ausentes - set(fixas_ausentes)); random.shuffle(resto_ausentes)
    g1_aus = resto_ausentes[:4]; g2_aus = resto_ausentes[4:]

    jogos_finais = []
    # Criação dos jogos com tipo e tipo_limpo
    j1 = list(set(fixas_sorteadas) | set(g1_sort) | set(fixas_ausentes) | set(g1_aus)); 
    jogos_finais.append({'tipo': 'M25 - Jogo 1 (G1+G1) 🎱', 'tipo_limpo': 'M25 - Jogo 1', 'numeros': sorted(j1)})
    
    j2 = list(set(fixas_sorteadas) | set(g1_sort) | set(fixas_ausentes) | set(g2_aus)); 
    jogos_finais.append({'tipo': 'M25 - Jogo 2 (G1+G2) 🎱', 'tipo_limpo': 'M25 - Jogo 2', 'numeros': sorted(j2)})
    
    j3 = list(set(fixas_sorteadas) | set(g2_sort) | set(fixas_ausentes) | set(g1_aus)); 
    jogos_finais.append({'tipo': 'M25 - Jogo 3 (G2+G1) 🎱', 'tipo_limpo': 'M25 - Jogo 3', 'numeros': sorted(j3)})
    
    j4 = list(set(fixas_sorteadas) | set(g2_sort) | set(fixas_ausentes) | set(g2_aus)); 
    jogos_finais.append({'tipo': 'M25 - Jogo 4 (G2+G2) 🎱', 'tipo_limpo': 'M25 - Jogo 4', 'numeros': sorted(j4)})

    jogos_view = []
    for j in jogos_finais:
        nums_fmt = ", ".join([f"{n:02d}" for n in j['numeros']])
        jogos_view.append({
            'tipo': j['tipo'], 
            'tipo_limpo': j['tipo_limpo'],
            'numeros': j['numeros'], 
            'numeros_str': nums_fmt, 
            'zap': f"{j['tipo']}: {nums_fmt}"
        })

    stats = obter_estatisticas(10)
    chart_labels = [f"{x[0]:02d}" for x in stats]
    chart_data = [x[1] for x in stats]

    flash("Método 25 Dezenas gerado com sucesso! (4 Jogos)", "success")
    return render_template('index.html', jogos=jogos_view, estatisticas=stats, filtro_atual=10, chart_labels=chart_labels, chart_data=chart_data, ultimo_concurso_db=ultimo_concurso_db)

# --- SURPRESINHA (MODIFICADA: TIPO LIMPO) ---
@app.route('/surpresinha', methods=['POST'])
def surpresinha():
    ultimo_concurso_db = ResultadoLotofacil.query.order_by(ResultadoLotofacil.concurso.desc()).first()

    try: qtd_jogos = int(request.form.get('qtd_surpresa', 1))
    except ValueError: qtd_jogos = 1
    if qtd_jogos < 1: qtd_jogos = 1
    if qtd_jogos > 50: qtd_jogos = 50 

    jogos = []
    for i in range(qtd_jogos):
        nums = sorted(random.sample(range(1, 26), 15))
        nums_fmt = ", ".join([f"{n:02d}" for n in nums])
        letra = chr(65 + i) if i < 26 else f"#{i+1}"
        jogos.append({
            'tipo': f'Surpresinha {letra} 🎲', 
            'tipo_limpo': f'Surpresinha {letra}', # Sem emoji
            'numeros': nums, 
            'numeros_str': nums_fmt, 
            'zap': f"Surpresa {letra}: {nums_fmt}"
        })
    
    stats = obter_estatisticas(10)
    chart_labels = [f"{x[0]:02d}" for x in stats]
    chart_data = [x[1] for x in stats]
    
    flash(f"{len(jogos)} Surpresinhas geradas! Boa sorte 🍀", "success")
    return render_template('index.html', jogos=jogos, estatisticas=stats, filtro_atual=10, chart_labels=chart_labels, chart_data=chart_data, ultimo_concurso_db=ultimo_concurso_db)

@app.route('/simular', methods=['POST'])
def simular():
    try:
        entrada = request.form.get('dezenas_simular')
        filtro_sim = int(request.form.get('filtro_simulacao', 10))
        meus_nums = set(int(n) for n in re.findall(r'\d+', entrada))
        if len(meus_nums) != 15: return jsonify({'success': False, 'message': 'Digite 15 números válidos.'})
        query = ResultadoLotofacil.query.order_by(ResultadoLotofacil.concurso.desc())
        if filtro_sim > 0: resultados = query.limit(filtro_sim).all()
        else: resultados = query.all()
        analise = {11: 0, 12: 0, 13: 0, 14: 0, 15: 0}
        for res in resultados:
            acertos = len(meus_nums.intersection(set(int(n) for n in re.findall(r'\d+', res.dezenas))))
            if acertos >= 11: analise[acertos] += 1
        msg = f"Nos últimos {len(resultados)} concursos:<br>15 Pontos: <b>{analise[15]}x</b><br>14 Pontos: <b>{analise[14]}x</b><br>13 Pontos: <b>{analise[13]}x</b><br>12 Pontos: <b>{analise[12]}x</b><br>11 Pontos: <b>{analise[11]}x</b>"
        return jsonify({'success': True, 'message': msg})
    except Exception as e: return jsonify({'success': False, 'message': str(e)})

@app.route('/salvar-jogo', methods=['POST'])
@login_required
def salvar_jogo():
    # AQUI: O tipo_limpo será enviado pelo formulário ou JS
    db.session.add(JogoSalvo(numeros=request.form.get('numeros_salvar'), tipo=request.form.get('tipo_salvar'), dono=current_user))
    db.session.commit()
    return jsonify({'success': True})

@app.route('/salvar-multiplos', methods=['POST'])
@login_required
def salvar_multiplos():
    dados = request.json.get('jogos', [])
    if not dados: return jsonify({'success': False})
    for j in dados: db.session.add(JogoSalvo(numeros=j['numeros'], tipo=j['tipo'], dono=current_user))
    db.session.commit()
    return jsonify({'success': True, 'message': f'{len(dados)} jogos salvos!'})

# --- IA ---
@app.route('/ia-chat', methods=['POST'])
def ia_chat():
    if not client: return jsonify({'resposta': "A IA não foi configurada."})
    try:
        mensagem_usuario = request.json.get('msg', '')
        CONTEXTO_ESPECIALISTA = """
        VOCÊ É O 'CONSULTOR GR', ESPECIALISTA EM LOTOFÁCIL.
        IMPORTANTE: Sempre que o usuário pedir para "fazer uma aposta", pergunte:
        "Qual estratégia você prefere? Padrão, Pura ou Método 25?"
        Conhecimentos:
        1. Padrão: Fixos e Aleatórios.
        2. Método 25 (Novo): 3 Fixas Sorteadas + 2 Fixas Ausentes. Gera 4 jogos.
        3. Pura: Analisa os últimos 10 concursos. Gera 3 jogos (Lógica, Equilíbrio, Meio).
        """
        prompt = f"{CONTEXTO_ESPECIALISTA}\n\nUsuário: {mensagem_usuario}\nConsultor GR:"
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        return jsonify({'resposta': response.text.replace('\n', '<br>')})
    except Exception as e: return jsonify({'resposta': "Erro na IA. Tente novamente."})

# --- OUTROS (Admin, Login, etc) ---
@app.route('/admin')
@login_required
def admin_panel():
    if not current_user.is_admin: return redirect(url_for('index'))
    users = User.query.all()
    busca = request.args.get('q', '')
    query_res = ResultadoLotofacil.query.order_by(ResultadoLotofacil.concurso.desc())
    if busca:
        if busca.isdigit(): query_res = query_res.filter_by(concurso=int(busca))
        else: query_res = query_res.filter(ResultadoLotofacil.data_sorteio.contains(busca))
    resultados = query_res.all() if busca else query_res.limit(20).all()
    return render_template('admin.html', usuarios=users, resultados=resultados, busca=busca, total_res=len(resultados) if busca else ResultadoLotofacil.query.count())

@app.route('/admin/novo-resultado', methods=['POST'])
@login_required
def admin_novo_resultado():
    if not current_user.is_admin: return redirect(url_for('index'))
    try:
        lista_nums = sorted(list(set(int(n) for n in re.findall(r'\d+', request.form.get('dezenas')))))
        if len(lista_nums) != 15: raise ValueError
        novo = ResultadoLotofacil(concurso=request.form.get('concurso'), data_sorteio=request.form.get('data'), dezenas=", ".join([f"{n:02d}" for n in lista_nums]))
        db.session.add(novo)
        db.session.commit(); flash('Cadastrado!', 'success')
    except: flash('Erro ao cadastrar.', 'danger')
    return redirect(url_for('admin_panel'))

@app.route('/admin/excluir-resultado/<int:id>', methods=['POST'])
@login_required
def admin_excluir_resultado(id):
    if not current_user.is_admin: return redirect(url_for('index'))
    res = db.session.get(ResultadoLotofacil, id)
    if res: db.session.delete(res); db.session.commit(); flash('Excluído.', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/virar-admin')
@login_required
def virar_admin():
    current_user.is_admin = True; db.session.commit(); flash(f'Parabéns {current_user.nome}! Você agora é Admin.', 'success'); return redirect(url_for('admin_panel'))

@app.route('/meus-jogos')
@login_required
def meus_jogos():
    meus_jogos = JogoSalvo.query.filter_by(user_id=current_user.id).order_by(JogoSalvo.data_criacao.desc()).all()
    ultimos_resultados = ResultadoLotofacil.query.order_by(ResultadoLotofacil.concurso.desc()).limit(50).all()
    return render_template('perfil.html', jogos=meus_jogos, ultimos_resultados=ultimos_resultados)

@app.route('/conferir', methods=['POST'])
@login_required
def conferir():
    oficial = set(int(n) for n in re.findall(r'\d+', request.form.get('resultado_oficial', '')))
    if len(oficial) != 15: flash('Precisa de 15 números para conferir.', 'danger'); return redirect(url_for('meus_jogos'))
    data_filtro = request.form.get('data_filtro') 
    query = JogoSalvo.query.filter_by(user_id=current_user.id)
    if data_filtro: query = query.filter(func.date(JogoSalvo.data_criacao) == data_filtro)
    jogos = query.order_by(JogoSalvo.data_criacao.desc()).all()
    mapa = {j.id: len(set(int(n) for n in re.findall(r'\d+', j.numeros)).intersection(oficial)) for j in jogos}
    if not jogos and data_filtro: flash(f'Nenhum jogo encontrado na data {data_filtro}.', 'warning')
    return render_template('perfil.html', jogos=jogos, resultado_oficial=sorted(list(oficial)), mapa_acertos=mapa, ultimos_resultados=ResultadoLotofacil.query.order_by(ResultadoLotofacil.concurso.desc()).limit(50).all(), data_filtro_atual=data_filtro)

@app.route('/resultados')
def resultados():
    page = request.args.get('page', 1, type=int)
    busca = request.args.get('q', '')
    query = ResultadoLotofacil.query.order_by(ResultadoLotofacil.concurso.desc())
    if busca:
        if busca.isdigit(): query = query.filter_by(concurso=int(busca))
        else: query = query.filter(ResultadoLotofacil.data_sorteio.contains(busca))
    pagination = query.paginate(page=page, per_page=20, error_out=False)
    return render_template('resultados.html', pagination=pagination, busca=busca)

@app.route('/editar-perfil', methods=['POST'])
@login_required
def editar_perfil():
    user = db.session.get(User, current_user.id)
    user.nome = request.form.get('nome'); user.telefone = request.form.get('telefone')
    if 'foto' in request.files:
        file = request.files['foto']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], f"user_{user.id}_{filename}"))
            user.foto_perfil = f"user_{user.id}_{filename}"
    db.session.commit(); flash('Atualizado!', 'success'); return redirect(url_for('meus_jogos'))

@app.route('/excluir-jogo/<int:id>', methods=['POST'])
@login_required
def excluir_jogo(id):
    jogo = db.session.get(JogoSalvo, id)
    if jogo and jogo.user_id == current_user.id: db.session.delete(jogo); db.session.commit(); flash('Excluído.', 'success')
    return redirect(url_for('meus_jogos'))

@app.route('/excluir-todos', methods=['POST'])
@login_required
def excluir_todos():
    if not check_password_hash(current_user.senha, request.form.get('senha_confirmacao')): flash('Senha errada.', 'danger'); return redirect(url_for('meus_jogos'))
    JogoSalvo.query.filter_by(user_id=current_user.id).delete(); db.session.commit(); flash('Limpo.', 'success'); return redirect(url_for('meus_jogos'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user and check_password_hash(user.senha, request.form.get('senha')): login_user(user); return redirect(url_for('meus_jogos'))
        flash('Erro no login.', 'danger')
    return render_template('login.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        if User.query.filter_by(email=request.form.get('email')).first(): flash('Email existe.', 'warning'); return redirect(url_for('registro'))
        db.session.add(User(nome=request.form.get('nome'), email=request.form.get('email'), telefone=request.form.get('telefone'), senha=generate_password_hash(request.form.get('senha'))))
        db.session.commit(); flash('Criado!', 'success'); return redirect(url_for('login'))
    return render_template('registro.html')

@app.route('/logout')
@login_required
def logout(): logout_user(); return redirect(url_for('index'))

@app.route('/exportar/<formato>')
@login_required
def exportar(formato):
    jogos = JogoSalvo.query.filter_by(user_id=current_user.id).all()
    dados = [{"Data": j.data_criacao.strftime("%d/%m/%Y"), "Estratégia": j.tipo, "Dezenas": j.numeros} for j in jogos]
    if formato == 'excel':
        output = io.BytesIO(); pd.DataFrame(dados).to_excel(output, index=False); output.seek(0)
        return send_file(output, download_name="historico.xlsx", as_attachment=True)
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", size=12)
    for d in dados: pdf.cell(0, 10, f"{d['Data']} | {d['Dezenas']}", 1, 1)
    return send_file(io.BytesIO(pdf.output(dest='S').encode('latin1')), download_name="historico.pdf", as_attachment=True, mimetype='application/pdf')

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(debug=True)