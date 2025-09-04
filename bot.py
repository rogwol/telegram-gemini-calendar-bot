import os
import json
import logging
import re
from datetime import datetime, timedelta
import pytz
import telegram
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters, ConversationHandler
)
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Configura o logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- INÍCIO DA CONFIGURAÇÃO ---
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
TIMEZONE = 'America/Sao_Paulo'
# -----------------------------

# Configurações do Google API
SCOPES = ['https://www.googleapis.com/auth/calendar']
TOKEN_PATH = 'token.json'

# Configura a API do Gemini
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

# Estados da conversa
ASKING_DETAILS, ASKING_PARTICIPANT = range(2)

def prepare_event_details(details):
    if details.get('start') and isinstance(details['start'], dict) and details['start'].get('dateTime') and not details.get('end'):
        logger.info("Horário de início detectado, calculando horário de término padrão (1h)...")
        start_str = details['start']['dateTime']
        start_dt = datetime.fromisoformat(start_str)
        end_dt = start_dt + timedelta(hours=1)
        details['end'] = {
            'dateTime': end_dt.isoformat(),
            'timeZone': TIMEZONE
        }
    if 'attendees' in details and details['attendees'] is not None:
        valid_attendees = []
        for attendee in details['attendees']:
            if isinstance(attendee, dict) and 'email' in attendee:
                valid_attendees.append(attendee)
            elif isinstance(attendee, str) and '@' in attendee:
                 valid_attendees.append({'email': attendee})
        if not valid_attendees:
            del details['attendees']
        else:
            details['attendees'] = valid_attendees
    return details

def get_calendar_service():
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            logger.error("token.json inválido ou não encontrado. Execute o script de autenticação primeiro.")
            return None
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
    return build('calendar', 'v3', credentials=creds)

def create_calendar_event(event_details):
    service = get_calendar_service()
    if not service:
        return "Desculpe, não consegui me conectar à sua agenda."
    try:
        final_details = prepare_event_details(event_details)
        event = service.events().insert(
            calendarId='primary',
            body=final_details,
            sendNotifications=True
        ).execute()
        return f"✅ Evento criado com sucesso! Link: {event.get('htmlLink')}"
    except Exception as e:
        logger.error(f"Erro ao criar evento na agenda: {e}")
        return f"❌ Ocorreu um erro ao criar o evento. Detalhes: {e}"

def list_calendar_events(start_time, end_time):
    service = get_calendar_service()
    if not service:
        return "Desculpe, não consegui me conectar à sua agenda."
    try:
        events_result = service.events().list(
            calendarId='primary', timeMin=start_time, timeMax=end_time,
            singleEvents=True, orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        if not events:
            return "Nenhum evento encontrado para o período."
        response_text = "Seus próximos eventos são:\n\n"
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            dt_object = datetime.fromisoformat(start.replace("Z", "+00:00"))
            local_tz = pytz.timezone(TIMEZONE)
            local_dt = dt_object.astimezone(local_tz)
            formatted_time = local_dt.strftime('%d/%m às %H:%M')
            response_text += f"🗓️ *{event['summary']}*\n   - {formatted_time}\n"
        return response_text
    except Exception as e:
        logger.error(f"Erro ao listar eventos: {e}")
        return "Ocorreu um erro ao buscar seus eventos."

def analyze_user_request(text):
    tz = pytz.timezone(TIMEZONE)
    current_time = datetime.now(tz)
    prompt = f"""
    Analise o texto a seguir para determinar a intenção do usuário: "criar_evento", "listar_eventos", ou "conversa_geral".
    Hoje é {current_time.strftime('%A, %d de %B de %Y, %H:%M')}. O fuso horário de referência é {TIMEZONE}.
    Responda APENAS com um objeto JSON.

    Se a intenção for "criar_evento":
    - Extraia título (summary), data e hora de início (start.dateTime), e convidados (attendees).
    - O formato do horário deve ser ISO 8601 (YYYY-MM-DDTHH:MM:SS).
    - Convidados (attendees) deve ser uma LISTA DE STRINGS contendo apenas os emails. Ex: ["email1@exemplo.com", "email2@exemplo.com"]
    - Se alguma informação não for mencionada, retorne a estrutura da chave mas com o valor null. Ex: "summary": null, ou "start": {{"dateTime": null, "timeZone": "{TIMEZONE}"}}
    - Formato: {{"intent": "criar_evento", "details": {{"summary": "...", "start": {{"dateTime": "...", "timeZone": "{TIMEZONE}"}}, "attendees": ["email@exemplo.com"]}}}}

    Se a intenção for "listar_eventos":
    - Extraia o período (ex: "hoje", "semana").
    - Formato: {{"intent": "listar_eventos", "period": "hoje"}}

    Se não for nenhuma das anteriores, use "conversa_geral".
    - Formato: {{"intent": "conversa_geral"}}

    Texto: "{text}"
    """
    try:
        response = gemini_model.generate_content(prompt)
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if match:
            json_response_text = match.group(0)
            logger.info(f"Análise do Gemini: {json_response_text}")
            return json.loads(json_response_text)
        else:
            logger.error(f"Nenhum JSON encontrado na resposta da Gemini: {response.text}")
            return {"intent": "conversa_geral"}
    except Exception as e:
        logger.error(f"Erro na análise do Gemini: {e}")
        return {"intent": "conversa_geral"}

def handle_participant_response(update, context):
    """Processa a resposta do usuário sobre adicionar ou não um participante."""
    user_response = update.message.text
    user_response_lower = user_response.lower()

    if 'não' in user_response_lower or 'nao' in user_response_lower:
        update.message.reply_text("Ok, criando o evento sem participantes adicionais.")
    else:
        # Pega o título do evento salvo para dar contexto à IA
        summary = context.user_data.get('summary', 'o evento')
        
        # Cria uma frase completa para a IA entender o que queremos
        contextual_text = f"Adicionar participante {user_response} ao evento {summary}"
        logger.info(f"Enviando texto contextual para análise: '{contextual_text}'")

        # Analisa a frase completa
        analysis = analyze_user_request(contextual_text)
        new_attendees = analysis.get("details", {}).get("attendees")
        
        if new_attendees:
            if 'attendees' not in context.user_data:
                context.user_data['attendees'] = []
            context.user_data['attendees'].extend(new_attendees)
            update.message.reply_text(f"Ótimo, adicionei os participantes. Criando o evento agora...")
        else:
            update.message.reply_text("Não identifiquei um participante. Criando o evento como estava.")

    reply = create_calendar_event(context.user_data)
    update.message.reply_text(reply)
    context.user_data.clear()
    return ConversationHandler.END

def process_event_details(update, context):
    user_response = update.message.text
    new_analysis = analyze_user_request(user_response).get("details", {})
    
    logger.info(f"Dados antes da mesclagem: {context.user_data}")
    if new_analysis:
        for key, value in new_analysis.items():
            if value is not None:
                context.user_data[key] = value
    logger.info(f"Dados depois da mesclagem: {context.user_data}")
    
    ready_to_create = (
        context.user_data.get('summary') and
        isinstance(context.user_data.get('start'), dict) and
        context.user_data.get('start', {}).get('dateTime')
    )

    if ready_to_create:
        if not context.user_data.get('attendees'):
            update.message.reply_text("Tudo certo. Deseja incluir algum participante neste evento? (Se sim, me diga o e-mail. Se não, apenas diga 'não')")
            return ASKING_PARTICIPANT
        else:
            reply = create_calendar_event(context.user_data)
            update.message.reply_text(reply)
            context.user_data.clear()
            return ConversationHandler.END
    else:
        if not context.user_data.get('summary'):
            reply_text = "Qual seria o título do evento?"
        elif not (isinstance(context.user_data.get('start'), dict) and context.user_data.get('start', {}).get('dateTime')):
            reply_text = f"Perfeito. Para qual data e hora devo agendar '{context.user_data.get('summary')}'?"
        else:
            reply_text = "Ok, anotado. O que mais?"
        
        update.message.reply_text(reply_text)
        return ASKING_DETAILS

def cancel_conversation(update, context):
    update.message.reply_text("Criação de evento cancelada.")
    context.user_data.clear()
    return ConversationHandler.END

def route_message(update, context):
    user_text = update.message.text
    analysis = analyze_user_request(user_text)
    intent = analysis.get("intent")

    if intent == "listar_eventos":
        tz = pytz.timezone(TIMEZONE)
        now = datetime.now(tz)
        period = analysis.get("period", "hoje")
        if period == "semana":
            start_time = now.replace(hour=0, minute=0, second=0).isoformat()
            end_time = (now + timedelta(days=7)).replace(hour=23, minute=59, second=59).isoformat()
        else:
            start_time = now.replace(hour=0, minute=0, second=0).isoformat()
            end_time = now.replace(hour=23, minute=59, second=59).isoformat()
        reply = list_calendar_events(start_time, end_time)
        update.message.reply_text(reply, parse_mode=telegram.ParseMode.MARKDOWN)

    elif intent == "criar_evento":
        details = analysis.get("details", {})
        ready_to_create = (
            details.get('summary') and
            isinstance(details.get('start'), dict) and
            details.get('start', {}).get('dateTime')
        )
        if ready_to_create:
            if not details.get('attendees'):
                context.user_data.update(details)
                update.message.reply_text("Tudo certo. Deseja incluir algum participante neste evento? (Se sim, me diga o e-mail. Se não, apenas diga 'não')")
                return ASKING_PARTICIPANT
            else:
                reply = create_calendar_event(details)
                update.message.reply_text(reply)
        else:
            context.user_data.update(details)
            if not details.get('summary'):
                reply_text = "Claro, vamos agendar. Qual o título do evento?"
            else:
                reply_text = f"Entendido. Para qual data e hora devo agendar o evento '{details.get('summary')}'?"
            update.message.reply_text(reply_text)
            return ASKING_DETAILS

    else: # conversa_geral
        response = gemini_model.generate_content(user_text)
        update.message.reply_text(response.text)

def start_command(update, context):
    update.message.reply_text('Olá! Sou seu assistente pessoal. Peça para adicionar um evento, listar seus compromissos ou me faça uma pergunta.')

def main():
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(Filters.text & ~Filters.command, route_message)],
        states={
            ASKING_DETAILS: [MessageHandler(Filters.text & ~Filters.command, process_event_details)],
            ASKING_PARTICIPANT: [MessageHandler(Filters.text & ~Filters.command, handle_participant_response)]
        },
        fallbacks=[CommandHandler('cancelar', cancel_conversation)],
        map_to_parent={ ConversationHandler.END: 0 }
    )
    
    dp.add_handler(CommandHandler("start", start_command))
    dp.add_handler(conv_handler)

    updater.start_polling()
    logger.info("Bot assistente com lógica de roteamento iniciado...")
    updater.idle()

if __name__ == '__main__':
    main()
