#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Telegram para alertas de jogos (TV aberta + streaming gratuito)
Fonte: mantosdofutebol.com.br
Compatível: Python 3.13 + python-telegram-bot 21.4
"""

import asyncio
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ========= CONFIG =========
TELEGRAM_TOKEN = "8323497835:AAFOux-nsKbdycoeOsFfTRimjkK3bu-7yb4"
CHAT_ID = "1531048903"

CHECK_INTERVAL = 25 * 60  # 25 minutos
alerta_minutos = 10

URLS = {
    "hoje": "https://mantosdofutebol.com.br/guia-de-jogos-tv-hoje-ao-vivo/",
    "amanha": "https://mantosdofutebol.com.br/jogos-de-amanha-tv/",
}

CANAIS_ABERTOS = ["Globo", "Band", "SBT", "Record", "RedeTV", "Cultura"]
LINKS_STREAMING = {
    "CazéTV": "https://www.youtube.com/@CazeTV",
    "Canal Goat": "https://www.youtube.com/@canalgoatbr",
    "Desimpedidos": "https://www.youtube.com/@desimpedidos",
    "NSports": "https://www.youtube.com/@NSPORTS_OFICIAL",
    "Sportynet": "https://www.youtube.com/@SportyNetBrasil",
    "FIFA+": "https://www.fifa.com/fifaplus/",
}

# ========= AUXILIARES =========
def normalizar_canal(texto: str) -> str:
    texto = re.sub(r"https?://\S+", "", texto)
    texto = re.sub(r"e\s*Youtube\.com/[^\s]+", "", texto)
    texto = re.sub(r"\s*Youtube\.com/[^\s]+", "", texto)
    return texto.strip()

def detectar_streaming_gratuito(canal_texto: str):
    encontrados = []
    for nome in LINKS_STREAMING:
        if nome.lower().replace(" ", "") in canal_texto.lower().replace(" ", ""):
            encontrados.append(nome)
    return encontrados

def coletar_jogos(url: str):
    """Extrai lista de jogos (hora, partida, canais, streamings)."""
    jogos = []
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        for tag in soup.find_all(["strong", "h3", "p"]):
            texto = tag.get_text(strip=True)
            if not texto:
                continue

            match = re.search(r"^(\d{1,2})h(\d{2})?", texto.replace(" ", ""))
            if not match:
                continue

            h = int(match.group(1))
            m = int(match.group(2)) if match.group(2) else 0
            hora = f"{h:02d}h{m:02d}"
            resto = texto[len(match.group(0)):].lstrip(" -–:").strip()

            canal_tag = tag.find_next("p")
            canal_texto = ""
            if canal_tag:
                canal_texto = canal_tag.get_text(strip=True).replace("Canais:", "")
                canal_texto = normalizar_canal(canal_texto)

            if not canal_texto:
                continue

            tem_aberto = any(canal in canal_texto for canal in CANAIS_ABERTOS)
            streams = detectar_streaming_gratuito(canal_texto)

            if tem_aberto or streams:
                jogos.append({
                    "hora": hora,
                    "partida": resto,
                    "canais": canal_texto,
                    "streams": streams,
                })

        # ✅ Remove duplicados (hora + partida)
        unicos = []
        vistos = set()
        for j in jogos:
            chave = (j["hora"], j["partida"])
            if chave not in vistos:
                vistos.add(chave)
                unicos.append(j)
        jogos = unicos

    except Exception as e:
        print(f"⚠️ Erro ao coletar {url}: {e}")
    return jogos

def formatar_jogos(jogos, dia_label):
    if not jogos:
        return f"⚠️ Nenhum jogo gratuito encontrado para {dia_label}."

    data = datetime.now().strftime("%d/%m/%Y")
    msg = f"📅 *Jogos de {dia_label} — {data}*\n" + "—" * 35 + "\n"

    abertos = [j for j in jogos if any(c in j["canais"] for c in CANAIS_ABERTOS)]
    gratis = [j for j in jogos if j["streams"] and not any(c in j["canais"] for c in CANAIS_ABERTOS)]

    if abertos:
        msg += "📺 *TV Aberta*\n"
        for j in abertos:
            msg += f"⏰ {j['hora']} — {j['partida']}\n🎥 {j['canais']}\n\n"
    else:
        msg += "📺 Nenhum jogo na TV aberta.\n\n"

    if gratis:
        msg += "🌐 *Streaming Gratuito*\n"
        for j in gratis:
            links = "\n🔗 ".join(
                [f"{s}: {LINKS_STREAMING.get(s, 'link')}" for s in j["streams"]]
            )
            msg += f"⏰ {j['hora']} — {j['partida']}\n🎥 {j['canais']}\n🔗 {links}\n\n"
    else:
        msg += "🌐 Nenhum jogo em streaming gratuito.\n"

    return msg

# ========= ALERTAS =========
async def enviar_alertas(bot):
    """Verifica jogos e envia alerta minutos antes."""
    jogos = coletar_jogos(URLS["hoje"])
    agora = datetime.now()

    for j in jogos:
        try:
            h, m = map(int, j["hora"].split("h"))
            hora_jogo = agora.replace(hour=h, minute=m, second=0, microsecond=0)
            if hora_jogo < agora - timedelta(hours=3):
                hora_jogo += timedelta(days=1)

            delta = (hora_jogo - agora).total_seconds()
            if 0 <= delta <= alerta_minutos * 60:
                links = "\n🔗 ".join(
                    [f"{s}: {LINKS_STREAMING.get(s, 'link')}" for s in j["streams"]]
                ) if j["streams"] else ""
                msg = (
                    f"🚨 *Começa em {alerta_minutos} minutos!*\n"
                    f"⏰ {j['hora']} — {j['partida']}\n"
                    f"📺 {j['canais']}\n"
                    f"{'🔗 ' + links if links else ''}"
                )
                await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
        except Exception as e:
            print(f"❌ Falha no alerta: {e}")

async def loop_alertas(bot):
    """Loop contínuo de monitoramento sem travar o app."""
    print("⏲️ Monitoramento de alertas iniciado.")
    while True:
        await enviar_alertas(bot)
        await asyncio.sleep(CHECK_INTERVAL)

# ========= COMANDOS =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚽ *Bot de Jogos ao Vivo*\n\n"
        "/hoje — Jogos de hoje\n"
        "/amanha — Jogos de amanhã\n"
        "/alerta 10 — Definir minutos antes do aviso\n\n"
        "🔔 Alertas automáticos estão ativos!",
        parse_mode="Markdown",
    )

async def cmd_hoje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jogos = coletar_jogos(URLS["hoje"])
    msg = formatar_jogos(jogos, "Hoje")
    await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)

async def cmd_amanha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jogos = coletar_jogos(URLS["amanha"])
    msg = formatar_jogos(jogos, "Amanhã")
    await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)

async def cmd_alerta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global alerta_minutos
    try:
        novo = int(context.args[0])
        if 1 <= novo <= 120:
            alerta_minutos = novo
            await update.message.reply_text(
                f"✅ Alerta ajustado para *{alerta_minutos} minutos* antes.",
                parse_mode="Markdown",
            )
        else:
            raise ValueError
    except Exception:
        await update.message.reply_text(
            "⚠️ Use: `/alerta 5` (valor entre 1 e 120)",
            parse_mode="Markdown",
        )

# ========= MAIN =========
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("hoje", cmd_hoje))
    app.add_handler(CommandHandler("amanha", cmd_amanha))
    app.add_handler(CommandHandler("alerta", cmd_alerta))

    async def on_startup(app):
        asyncio.create_task(loop_alertas(app.bot))
        await app.bot.send_message(chat_id=CHAT_ID, text="✅ Bot iniciado com sucesso!", parse_mode="Markdown")
        await app.bot.send_message(
            chat_id=CHAT_ID,
            text=(
                "⚽ *Bot de Jogos ao Vivo*\n\n"
                "/hoje — Jogos de hoje\n"
                "/amanha — Jogos de amanhã\n"
                "/alerta 10 — Definir minutos antes do aviso\n\n"
                "🔔 Alertas automáticos estão ativos!"
            ),
            parse_mode="Markdown",
        )

    app.post_init = on_startup
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
