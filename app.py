"""
Support AI - Sistema de Suporte TI com IA Real
Powered by Groq + Llama 3 Vision
"""

import streamlit as st
import random
import re
import json
import base64
import os
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

try:
    from groq import Groq
    GROQ_OK = True
except ImportError:
    GROQ_OK = False

# ========== CONFIGURAÇÕES ==========
DOCS_DIR         = Path("./documentos")
BASE_APRENDIZADO = DOCS_DIR / "base_aprendizado.txt"
FILA_APROVACAO   = DOCS_DIR / "fila_aprovacao.json"
HISTORICO_FILE   = DOCS_DIR / "historico.json"

GROQ_API_KEY  = os.getenv("GROQ_API_KEY", "")
SENHA_ADMIN   = os.getenv("ADMIN_SENHA", "digifarma")

# WhatsApp Callmebot
WA_PHONE      = os.getenv("WA_PHONE", "")       # ex: 5531999999999
WA_APIKEY     = os.getenv("WA_APIKEY", "")       # chave do callmebot

# Email Gmail
EMAIL_REMETENTE = os.getenv("EMAIL_REMETENTE", "")   # seu gmail
EMAIL_SENHA     = os.getenv("EMAIL_SENHA", "")        # senha de app gmail
EMAIL_DESTINO   = os.getenv("EMAIL_DESTINO", "")      # email que recebe

MINHA_FRASE = "Pega esse trem aqui e faz isso que vai dar certo"

FRASES_PENSANDO = [
    "Consultando base de conhecimento...",
    "Analisando o problema...",
    "Cruzando informações...",
    "Procurando a melhor solução...",
]

# ========== SETUP ==========
def garantir_estrutura():
    DOCS_DIR.mkdir(exist_ok=True)
    if not BASE_APRENDIZADO.exists():
        BASE_APRENDIZADO.write_text("# Base de Aprendizado - Support AI\n\n", encoding="utf-8")
    if not FILA_APROVACAO.exists():
        FILA_APROVACAO.write_text("[]", encoding="utf-8")
    if not HISTORICO_FILE.exists():
        HISTORICO_FILE.write_text("[]", encoding="utf-8")

# ========== NOTIFICAÇÕES ==========
def enviar_whatsapp(mensagem: str):
    if not WA_PHONE or not WA_APIKEY:
        return False
    try:
        url = f"https://api.callmebot.com/whatsapp.php?phone={WA_PHONE}&text={requests.utils.quote(mensagem)}&apikey={WA_APIKEY}"
        r = requests.get(url, timeout=10)
        return r.status_code == 200
    except Exception:
        return False

def enviar_email(assunto: str, corpo: str):
    if not EMAIL_REMETENTE or not EMAIL_SENHA or not EMAIL_DESTINO:
        return False
    try:
        msg = MIMEMultipart()
        msg["From"]    = EMAIL_REMETENTE
        msg["To"]      = EMAIL_DESTINO
        msg["Subject"] = assunto
        msg.attach(MIMEText(corpo, "plain", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_REMETENTE, EMAIL_SENHA)
            server.sendmail(EMAIL_REMETENTE, EMAIL_DESTINO, msg.as_string())
        return True
    except Exception:
        return False

def notificar_sugestao(atendente: str, pergunta: str, sugestao: str):
    """Notifica por WhatsApp e email quando chega sugestão pendente"""
    data = datetime.now().strftime("%d/%m/%Y %H:%M")
    msg  = (
        f"🔔 Support AI - Nova sugestão pendente!\n\n"
        f"👤 Atendente: {atendente}\n"
        f"🕐 Data: {data}\n\n"
        f"❓ Pergunta: {pergunta}\n\n"
        f"💡 Sugestão: {sugestao}\n\n"
        f"Acesse o painel Admin para aprovar ou rejeitar."
    )
    enviar_whatsapp(msg)
    enviar_email(
        assunto=f"[Support AI] Nova sugestão de {atendente} aguardando aprovação",
        corpo=msg
    )

# ========== IA ==========
def busca_rapida(pergunta: str) -> str:
    pergunta_lower = pergunta.lower()
    palavras = [p for p in re.split(r'\W+', pergunta_lower) if len(p) > 3]
    if not palavras:
        conteudo = ""
        for arq in sorted(DOCS_DIR.glob("*.txt")):
            try: conteudo += arq.read_text(encoding="utf-8", errors="ignore")
            except: pass
        return conteudo[:8000]

    trechos = []
    for arq in sorted(DOCS_DIR.glob("*.txt")):
        try:
            texto  = arq.read_text(encoding="utf-8", errors="ignore")
            blocos = re.split(r'\n(?=#{1,3}\s)', texto)
            for bloco in blocos:
                bloco_lower = bloco.lower()
                score = sum(3 if p in bloco_lower[:100] else 1 for p in palavras if p in bloco_lower)
                if score > 0:
                    trechos.append((score, f"[{arq.name}]\n{bloco.strip()}"))
        except: continue

    trechos.sort(key=lambda x: x[0], reverse=True)
    return "\n\n---\n\n".join(t[1] for t in trechos[:8]) or ""

def responder_com_ia(pergunta: str, imagem_base64: str = None) -> str:
    if not GROQ_OK:
        return "❌ Biblioteca `groq` não instalada. Rode: `pip install groq`"
    if not GROQ_API_KEY:
        return "❌ GROQ_API_KEY não configurada no .env"

    client   = Groq(api_key=GROQ_API_KEY)
    contexto = busca_rapida(pergunta)

    system_prompt = f"""Você é o Support AI, assistente especializado em suporte técnico do sistema Digifarma para farmácias.
Responda de forma direta, clara e prática em português brasileiro.
Se encontrar a solução, explique passo a passo. Se não tiver certeza, diga claramente.

BASE DE CONHECIMENTO:
{contexto}"""

    try:
        if imagem_base64:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": f"Analise este print de erro: {pergunta}"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{imagem_base64}"}}
                ]}
            ]
            response = client.chat.completions.create(
                model="llama-3.2-11b-vision-preview",
                messages=messages, max_tokens=1500, temperature=0.3
            )
        else:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": pergunta}
            ]
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages, max_tokens=1500, temperature=0.3
            )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ Erro na IA: {str(e)}"

# ========== DADOS ==========
def salvar_historico(pergunta, resposta, atendente, feedback=""):
    garantir_estrutura()
    try: historico = json.loads(HISTORICO_FILE.read_text(encoding="utf-8"))
    except: historico = []
    historico.append({
        "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "atendente": atendente,
        "pergunta": pergunta,
        "resposta": resposta[:300],
        "feedback": feedback
    })
    HISTORICO_FILE.write_text(json.dumps(historico[-500:], ensure_ascii=False, indent=2), encoding="utf-8")

def enviar_para_aprovacao(titulo: str, pergunta: str, sugestao: str, atendente: str):
    garantir_estrutura()
    try: fila = json.loads(FILA_APROVACAO.read_text(encoding="utf-8"))
    except: fila = []
    fila.append({
        "id":       datetime.now().strftime("%Y%m%d%H%M%S"),
        "data":     datetime.now().strftime("%d/%m/%Y %H:%M"),
        "atendente": atendente,
        "titulo":   titulo,
        "pergunta": pergunta,
        "sugestao": sugestao,
        "status":   "pendente"
    })
    FILA_APROVACAO.write_text(json.dumps(fila, ensure_ascii=False, indent=2), encoding="utf-8")
    # Notifica por WhatsApp + email
    notificar_sugestao(atendente, pergunta, sugestao)

def aprovar_sugestao(item_id):
    try:
        fila = json.loads(FILA_APROVACAO.read_text(encoding="utf-8"))
        for item in fila:
            if item["id"] == item_id:
                item["status"] = "aprovado"
                titulo  = item.get("titulo", item["pergunta"][:60])
                entrada = (
                    f"\n### {titulo}\n"
                    f"DATA: {item['data']} | ATENDENTE: {item['atendente']}\n"
                    f"PROBLEMA: {item['pergunta']}\n"
                    f"SOLUÇÃO: {item['sugestao']}\n"
                )
                with open(BASE_APRENDIZADO, "a", encoding="utf-8") as f:
                    f.write(entrada)
        FILA_APROVACAO.write_text(json.dumps(fila, ensure_ascii=False, indent=2), encoding="utf-8")
    except: pass

def rejeitar_sugestao(item_id):
    try:
        fila = json.loads(FILA_APROVACAO.read_text(encoding="utf-8"))
        for item in fila:
            if item["id"] == item_id:
                item["status"] = "rejeitado"
        FILA_APROVACAO.write_text(json.dumps(fila, ensure_ascii=False, indent=2), encoding="utf-8")
    except: pass

def contar_pendentes():
    try:
        fila = json.loads(FILA_APROVACAO.read_text(encoding="utf-8"))
        return sum(1 for i in fila if i["status"] == "pendente")
    except: return 0

def contar_entradas():
    total = 0
    for arq in DOCS_DIR.glob("*.txt"):
        try:
            txt = arq.read_text(encoding="utf-8", errors="ignore")
            total += len(re.findall(r'^#{1,3}\s+', txt, re.MULTILINE))
        except: pass
    return total

# ========== CONFIG STREAMLIT ==========
st.set_page_config(page_title="Support AI", page_icon="🖥️", layout="wide")
garantir_estrutura()

# ========== CSS ==========
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Sora:wght@400;500;600;700&display=swap');

* { box-sizing: border-box; }
.stApp { background-color: #090E1A; font-family: 'Sora', sans-serif; }

section[data-testid="stSidebar"] {
    background-color: #0D1424 !important;
    border-right: 1px solid #1E2D4A;
}
.chat-container {
    height: calc(100vh - 300px);
    overflow-y: auto;
    padding: 0 4px 16px 4px;
    display: flex;
    flex-direction: column;
    scroll-behavior: smooth;
}
.message-user {
    background: linear-gradient(135deg,#1A4FCC,#0F3399);
    color: white; padding: 12px 16px;
    border-radius: 18px 18px 4px 18px;
    margin: 6px 0 6px 15%; font-size: 0.88rem;
    box-shadow: 0 3px 12px rgba(26,79,204,0.25);
    border: 1px solid #2558D4; word-wrap: break-word;
}
.message-bot {
    background: #0D1424; border: 1px solid #1E2D4A;
    padding: 14px 16px;
    border-radius: 4px 18px 18px 18px;
    margin: 6px 15% 6px 0;
    color: #C8D8F0; font-size: 0.88rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    word-wrap: break-word;
}
.message-bot code {
    background:#060B14; color:#5BB8FF;
    padding:2px 6px; border-radius:4px;
    font-family:'JetBrains Mono',monospace;
    font-size:0.78rem; border:1px solid #1E2D4A;
}
.message-bot pre {
    background:#060B14; border:1px solid #1E2D4A;
    padding:10px; border-radius:8px; overflow-x:auto;
    font-family:'JetBrains Mono',monospace;
    font-size:0.78rem; color:#7EC8E3;
}
.sugestao-box {
    background:#0D1A0D; border:1px solid #1A4A1A;
    border-left:3px solid #2EA043;
    border-radius:8px; padding:12px 14px;
    margin:6px 0; color:#90C090; font-size:0.83rem;
}
.pendente-box {
    background:#1A1200; border:1px solid #4A3800;
    border-left:4px solid #F0A000;
    border-radius:8px; padding:14px; margin:8px 0; color:#D4AA50;
}
.header-bar {
    background: linear-gradient(135deg,#0D1424,#0A1628);
    border:1px solid #1E2D4A; border-radius:10px;
    padding:10px 16px; margin-bottom:10px;
    display:flex; align-items:center; gap:10px;
}
.header-bar h1 {
    font-family:'JetBrains Mono',monospace;
    font-size:1.1rem; font-weight:600; color:#4D9FFF; margin:0;
}
.header-bar p { color:#4A6080; margin:0; font-size:0.75rem; }
.stButton > button {
    background:linear-gradient(135deg,#1A4FCC,#0F3399) !important;
    color:white !important; border:1px solid #2558D4 !important;
    border-radius:8px !important; font-weight:500 !important;
    font-size:0.82rem !important;
}
.stButton > button:hover {
    background:linear-gradient(135deg,#2558D4,#1A4FCC) !important;
}
.stTextArea textarea {
    background-color:#060B14 !important; color:#C8D8F0 !important;
    border:1px solid #1E2D4A !important; border-radius:10px !important;
    font-family:'Sora',sans-serif !important; font-size:0.88rem !important;
    resize:none !important;
}
.stTextArea textarea:focus {
    border-color:#4D9FFF !important;
    box-shadow:0 0 0 2px rgba(77,159,255,0.15) !important;
}
.stTextInput input {
    background-color:#060B14 !important; color:#C8D8F0 !important;
    border:1px solid #1E2D4A !important; border-radius:8px !important;
    font-family:'Sora',sans-serif !important;
}
.nome-tag {
    background:#0D1A2E; border:1px solid #1E2D4A;
    color:#4D9FFF; padding:4px 10px; border-radius:20px;
    font-size:0.75rem; font-family:'JetBrains Mono',monospace;
    display:inline-block;
}
.notif-info {
    background:#0A1628; border:1px solid #1E3A5F;
    border-left:3px solid #4D9FFF;
    border-radius:8px; padding:10px 14px;
    color:#7EB8FF; font-size:0.82rem; margin:8px 0;
}
.footer {
    text-align:center; color:#2A3D5A; font-size:10px;
    padding:8px 0 4px 0; font-family:'JetBrains Mono',monospace;
}
</style>
""", unsafe_allow_html=True)

# ========== SESSION STATE ==========
for k, v in {
    "messages": [], "atendente": "", "pagina": "chat",
    "aguardando_sugestao": False, "ultima_pergunta": "",
    "admin_logado": False, "processando": False
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ========== LOGIN ==========
if not st.session_state.atendente:
    st.markdown("""
    <div style="max-width:380px;margin:80px auto;text-align:center;">
        <div style="font-size:3.5rem;margin-bottom:1rem;">🖥️</div>
        <h2 style="color:#4D9FFF;font-family:'JetBrains Mono',monospace;margin-bottom:6px;">Support AI</h2>
        <p style="color:#4A6080;margin-bottom:2rem;font-size:0.9rem;">Suporte técnico Digifarma</p>
    </div>
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        nome = st.text_input("Seu nome:", placeholder="Ex: João Silva")
        if st.button("Entrar →", use_container_width=True):
            if nome.strip():
                st.session_state.atendente = nome.strip()
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"Olá, **{nome.strip()}**! 👋 Sou o Support AI.\n\nDescreva o erro — pode mandar texto ou um **print da tela**. 🧠"
                })
                st.rerun()
    st.stop()

# ========== SIDEBAR ==========
with st.sidebar:
    st.markdown(f"<div class='nome-tag'>👤 {st.session_state.atendente}</div>", unsafe_allow_html=True)
    st.caption(MINHA_FRASE)
    st.divider()

    pendentes = contar_pendentes()
    c1, c2 = st.columns(2)
    c1.metric("📚 Entradas", contar_entradas())
    c2.metric("⏳ Pendentes", pendentes)
    st.divider()

    if st.button("💬 Chat", use_container_width=True):
        st.session_state.pagina = "chat"; st.rerun()

    label_admin = f"🔐 Admin ({pendentes} ⏳)" if pendentes > 0 else "🔐 Admin"
    if st.button(label_admin, use_container_width=True):
        st.session_state.pagina = "admin"; st.rerun()

    st.divider()
    st.markdown("#### 💡 Exemplos")
    for ex in ["GTIN inválido", "certificado digital", "SADI não conecta", "troco negativo", "contingência"]:
        if st.button(ex, use_container_width=True, key=f"ex_{ex}"):
            st.session_state.messages.append({"role": "user", "content": ex})
            st.session_state.pagina = "chat"
            st.session_state.aguardando_sugestao = False
            st.session_state.processando = True
            st.session_state.ultima_pergunta = ex
            st.rerun()

    st.divider()
    if st.button("🗑️ Limpar chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.aguardando_sugestao = False
        st.rerun()
    if st.button("🚪 Sair", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

# ==========================================
# PÁGINA: CHAT
# ==========================================
if st.session_state.pagina == "chat":

    st.markdown("""
    <div class="header-bar">
        <span style="font-size:1.4rem">🖥️</span>
        <div><h1>Support AI</h1><p>Powered by Groq · Base Digifarma</p></div>
    </div>
    """, unsafe_allow_html=True)

    # Mensagens
    chat_html = '<div class="chat-container" id="chat-end">'
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            chat_html += f'<div class="message-user"><b>👤 {st.session_state.atendente}:</b><br>{msg["content"]}</div>'
        else:
            content = msg["content"].replace("\n", "<br>")
            chat_html += f'<div class="message-bot"><b>🖥️ Support AI:</b><br>{content}</div>'
    chat_html += '</div>'
    chat_html += '<script>var el=document.getElementById("chat-end");if(el)el.scrollTop=el.scrollHeight;</script>'
    st.markdown(chat_html, unsafe_allow_html=True)

    # Feedback
    if st.session_state.messages:
        last = st.session_state.messages[-1]
        if last["role"] == "assistant" and last.get("com_feedback"):
            st.markdown('<div style="margin-left:4px;margin-bottom:4px;color:#4A6080;font-size:0.8rem;">Essa resposta ajudou?</div>', unsafe_allow_html=True)
            fc1, fc2, fc3 = st.columns([1, 1, 6])
            with fc1:
                if st.button("✅ Resolveu", key="btn_ok"):
                    salvar_historico(st.session_state.ultima_pergunta, last["content"], st.session_state.atendente, "resolveu")
                    last["com_feedback"] = False
                    st.session_state.messages.append({"role": "assistant", "content": "Ótimo! Fico feliz que tenha resolvido 🎉"})
                    st.rerun()
            with fc2:
                if st.button("❌ Não resolveu", key="btn_nok"):
                    salvar_historico(st.session_state.ultima_pergunta, last["content"], st.session_state.atendente, "não resolveu")
                    last["com_feedback"] = False
                    st.session_state.aguardando_sugestao = True
                    st.rerun()

    # Formulário de sugestão com título + solução
    if st.session_state.aguardando_sugestao:
        st.markdown('<div class="sugestao-box"><b>🧠 Qual foi a solução correta?</b><br>Preencha o título e a solução — sua sugestão vai para aprovação!</div>', unsafe_allow_html=True)
        with st.form("form_sug"):
            titulo_sug = st.text_input(
                "Título do erro:",
                placeholder="Ex: GTIN inválido no módulo de vendas",
                value=st.session_state.ultima_pergunta[:80]
            )
            solucao_sug = st.text_area(
                "Solução passo a passo:",
                height=120,
                placeholder="1. Acesse...\n2. Clique em...\n3. Corrija..."
            )
            if st.form_submit_button("📤 Enviar sugestão", use_container_width=True):
                if titulo_sug.strip() and solucao_sug.strip():
                    enviar_para_aprovacao(
                        titulo   = titulo_sug,
                        pergunta = st.session_state.ultima_pergunta,
                        sugestao = solucao_sug,
                        atendente= st.session_state.atendente
                    )
                    st.session_state.aguardando_sugestao = False
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": "✅ Sugestão enviada para aprovação! Obrigado por contribuir 🙏"
                    })
                    st.rerun()
                else:
                    st.warning("Preencha o título e a solução.")

    # Processar resposta pendente
    if st.session_state.processando:
        st.session_state.processando = False
        with st.spinner(random.choice(FRASES_PENSANDO)):
            pergunta = st.session_state.ultima_pergunta
            resposta = responder_com_ia(pergunta)
        st.session_state.messages.append({"role": "assistant", "content": resposta, "com_feedback": True})
        salvar_historico(pergunta, resposta, st.session_state.atendente)
        st.rerun()

    # Upload discreto + chat_input limpo
    with st.expander("📎 Anexar print do erro"):
        uploaded = st.file_uploader("", type=["png","jpg","jpeg"],
                                     label_visibility="collapsed", key="uploader")
        if uploaded:
            st.image(uploaded, caption=uploaded.name, width=300)

    user_input = st.chat_input("Descreva o erro ou cole a mensagem exata...")

    if user_input:
        pergunta   = user_input.strip()
        imagem_b64 = None

        uploaded_ref = st.session_state.get("_uploaded_ref")
        if uploaded:
            uploaded.seek(0)
            imagem_b64 = base64.b64encode(uploaded.read()).decode("utf-8")
            pergunta   = user_input.strip() + " [print anexado]"

        st.session_state.messages.append({"role": "user", "content": pergunta})
        st.session_state.ultima_pergunta     = pergunta
        st.session_state.aguardando_sugestao = False
        st.session_state.processando         = True

        if imagem_b64:
            with st.spinner("Analisando imagem..."):
                resposta = responder_com_ia(pergunta, imagem_b64)
            st.session_state.messages.append({"role": "assistant", "content": resposta, "com_feedback": True})
            salvar_historico(pergunta, resposta, st.session_state.atendente)
            st.session_state.processando = False

        st.rerun()

    st.markdown('<div class="footer">Support AI · Digifarma · Powered by Groq</div>', unsafe_allow_html=True)

# ==========================================
# PÁGINA: ADMIN
# ==========================================
elif st.session_state.pagina == "admin":
    st.markdown("## 🔐 Painel Admin")

    if not st.session_state.admin_logado:
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            senha = st.text_input("Senha:", type="password")
            if st.button("Entrar", use_container_width=True):
                if senha == SENHA_ADMIN:
                    st.session_state.admin_logado = True
                    st.rerun()
                else:
                    st.error("Senha incorreta.")
    else:
        tab1, tab2, tab3 = st.tabs(["⏳ Aprovações", "📊 Histórico", "🔔 Notificações"])

        # --- APROVAÇÕES ---
        with tab1:
            try: fila = json.loads(FILA_APROVACAO.read_text(encoding="utf-8"))
            except: fila = []

            pendentes  = [i for i in fila if i["status"] == "pendente"]
            aprovados  = [i for i in fila if i["status"] == "aprovado"]
            rejeitados = [i for i in fila if i["status"] == "rejeitado"]

            c1, c2, c3 = st.columns(3)
            c1.metric("⏳ Pendentes",   len(pendentes))
            c2.metric("✅ Aprovadas",   len(aprovados))
            c3.metric("❌ Rejeitadas",  len(rejeitados))
            st.divider()

            if not pendentes:
                st.info("Nenhuma sugestão pendente ✅")
            for item in pendentes:
                st.markdown(f"""
                <div class="pendente-box">
                    <b>📋 {item['data']} · {item['atendente']}</b><br><br>
                    <b>Título:</b> {item.get('titulo', '—')}<br><br>
                    <b>Pergunta original:</b> {item['pergunta']}<br><br>
                    <b>Solução sugerida:</b> {item['sugestao']}
                </div>""", unsafe_allow_html=True)
                ca, cr = st.columns(2)
                with ca:
                    if st.button("✅ Aprovar", key=f"a_{item['id']}", use_container_width=True):
                        aprovar_sugestao(item["id"])
                        st.success("Aprovado e salvo na base!")
                        st.rerun()
                with cr:
                    if st.button("❌ Rejeitar", key=f"r_{item['id']}", use_container_width=True):
                        rejeitar_sugestao(item["id"])
                        st.warning("Rejeitado.")
                        st.rerun()

        # --- HISTÓRICO ---
        with tab2:
            try:
                historico = list(reversed(json.loads(HISTORICO_FILE.read_text(encoding="utf-8"))))
            except: historico = []

            if not historico:
                st.info("Nenhum atendimento ainda.")
            else:
                resolvidos     = sum(1 for h in historico if h.get("feedback") == "resolveu")
                nao_resolvidos = sum(1 for h in historico if h.get("feedback") == "não resolveu")
                c1, c2, c3 = st.columns(3)
                c1.metric("Total",              len(historico))
                c2.metric("✅ Resolvidos",       resolvidos)
                c3.metric("❌ Não resolvidos",   nao_resolvidos)
                st.divider()
                for h in historico[:100]:
                    fb    = h.get("feedback", "")
                    emoji = "✅" if fb == "resolveu" else "❌" if fb == "não resolveu" else "⏳"
                    with st.expander(f"{emoji} {h['data']} · {h['atendente']} · {h['pergunta'][:55]}"):
                        st.markdown(f"**Pergunta:** {h['pergunta']}")
                        st.markdown(f"**Resposta:** {h['resposta']}")
                        if fb: st.markdown(f"**Feedback:** {fb}")

        # --- NOTIFICAÇÕES ---
        with tab3:
            st.markdown("### 🔔 Configuração de Notificações")
            st.markdown("Configure no arquivo `.env` do projeto:")

            st.markdown("""
            <div class="notif-info">
            <b>WhatsApp via Callmebot (gratuito):</b><br><br>
            1. Mande uma mensagem para <b>+34 644 53 00 50</b> no WhatsApp:<br>
            &nbsp;&nbsp;&nbsp;<code>I allow callmebot to send me messages</code><br>
            2. Você vai receber sua <b>API Key</b><br>
            3. Adicione no .env:<br>
            &nbsp;&nbsp;&nbsp;<code>WA_PHONE=5531999999999</code> (seu número com DDI)<br>
            &nbsp;&nbsp;&nbsp;<code>WA_APIKEY=sua_chave_aqui</code>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("""
            <div class="notif-info">
            <b>Email via Gmail:</b><br><br>
            1. Ative a verificação em 2 etapas no Gmail<br>
            2. Acesse: Google Account > Segurança > Senhas de app<br>
            3. Gere uma senha de app para "Email"<br>
            4. Adicione no .env:<br>
            &nbsp;&nbsp;&nbsp;<code>EMAIL_REMETENTE=seuemail@gmail.com</code><br>
            &nbsp;&nbsp;&nbsp;<code>EMAIL_SENHA=senha_de_app_aqui</code><br>
            &nbsp;&nbsp;&nbsp;<code>EMAIL_DESTINO=destino@gmail.com</code>
            </div>
            """, unsafe_allow_html=True)

            # Teste de notificação
            st.divider()
            st.markdown("**Testar notificações:**")
            tc1, tc2 = st.columns(2)
            with tc1:
                if st.button("📱 Testar WhatsApp", use_container_width=True):
                    ok = enviar_whatsapp("🧪 Teste Support AI - WhatsApp funcionando!")
                    st.success("Enviado!") if ok else st.error("Falhou. Verifique WA_PHONE e WA_APIKEY no .env")
            with tc2:
                if st.button("📧 Testar Email", use_container_width=True):
                    ok = enviar_email("Teste Support AI", "Email de teste do Support AI funcionando!")
                    st.success("Enviado!") if ok else st.error("Falhou. Verifique EMAIL_REMETENTE, EMAIL_SENHA e EMAIL_DESTINO no .env")

        st.divider()
        if st.button("🚪 Sair do Admin"):
            st.session_state.admin_logado = False
            st.session_state.pagina = "chat"
            st.rerun()