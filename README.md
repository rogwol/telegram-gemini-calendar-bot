# Bot Assistente Pessoal para Telegram com Gemini e Google Calendar

Este repositório contém o código-fonte de um bot multifuncional para o Telegram, desenvolvido em Python. O bot atua como um assistente pessoal inteligente, utilizando a API do Google Gemini para processamento de linguagem natural e a API do Google Calendar para gerenciar eventos e compromissos.

O projeto foi construído passo a passo, superando desafios reais de configuração de servidor, autenticação de APIs, depuração de código e segurança, servindo como um estudo de caso prático para a criação de bots de IA integrados.

---

## ✨ Funcionalidades

* **Assistente de Conversação:** Utiliza o modelo `gemini-1.5-flash` para manter conversas gerais, responder a perguntas e realizar tarefas de linguagem.
* **Gerenciamento de Agenda (Google Calendar):**
    * **Listar Eventos:** Responde a perguntas como "o que tenho para hoje?" ou "quais meus compromissos da semana?".
    * **Criar Eventos:** Adiciona eventos na agenda do usuário através de linguagem natural (ex: "Adicionar reunião com joao@email.com amanhã às 15h").
    * **Conversa Interativa:** Caso um pedido de agendamento não contenha todas as informações necessárias (como data, hora ou título), o bot inicia um diálogo para coletar os detalhes que faltam.
* **Segurança:** Utiliza o fluxo OAuth 2.0 para autenticação segura com a API do Google, sem expor as credenciais do usuário. As chaves de API são gerenciadas através de variáveis de ambiente no servidor, e não no código.

---

## 🛠️ Tecnologias Utilizadas

* **Linguagem:** Python 3
* **Biblioteca do Telegram:** `python-telegram-bot`
* **IA e NLP:** Google Gemini API (`gemini-1.5-flash`)
* **Agenda:** Google Calendar API v3
* **Hospedagem:** VM na Oracle Cloud (Always Free Tier)
* **Persistência:** `tmux` para manter o bot rodando em segundo plano

---

## 🚀 Configuração e Instalação

Para executar sua própria instância deste bot, siga os passos abaixo.

### Pré-requisitos
* Python 3.9+
* Uma conta Telegram e um token de bot (obtido com o [@BotFather](https://telegram.me/BotFather)).
* Uma conta Google Cloud com um projeto criado.

### 1. Configuração do Google Cloud
1.  No seu projeto do Google Cloud, ative a **Google Gemini API** e a **Google Calendar API**.
2.  Crie uma **Chave de API** para o Gemini.
3.  Configure a **Tela de Consentimento OAuth** (tipo "Externo"), adicionando o escopo `https://www.googleapis.com/auth/calendar` e seu e-mail como usuário de teste.
4.  Crie uma credencial do tipo **ID do cliente OAuth** para "Aplicativo para computador" e baixe o arquivo `credentials.json`.

### 2. Autenticação Local
1.  Em seu computador local, crie uma pasta e coloque o arquivo `credentials.json` dentro dela.
2.  Crie um script `generate_token.py` (código disponível no histórico da nossa conversa) para gerar o arquivo `token.json` através do fluxo de autorização do navegador.

### 3. Configuração do Servidor
1.  Clone este repositório para o seu servidor.
2.  Crie um ambiente virtual Python: `python3 -m venv venv`.
3.  Ative o ambiente: `source venv/bin/activate`.
4.  Instale todas as dependências: `pip install -r requirements.txt`.
5.  Defina as variáveis de ambiente com suas chaves (ex: no `~/.bash_profile`):
    ```bash
    export TELEGRAM_BOT_TOKEN='SUA_CHAVE_AQUI'
    export GEMINI_API_KEY='SUA_CHAVE_AQUI'
    ```
6.  Use um cliente SFTP (como o WinSCP) para enviar os arquivos `credentials.json` e `token.json` para a pasta do projeto no servidor.

### 4. Execução
* Para iniciar o bot, execute:
    ```bash
    python3 bot.py
    ```
* Para mantê-lo rodando permanentemente, use o `tmux`:
    ```bash
    tmux new -s bot
    python3 bot.py
    # Para sair e deixar rodando: Ctrl+B e depois D
    ```

---

## 💬 Agradecimentos

Este projeto foi desenvolvido com a assistência intensiva e o acompanhamento passo a passo do **Gemini**, a IA conversacional do Google. Grande parte da arquitetura do código, da lógica de programação, da depuração de erros complexos e da implementação de funcionalidades foi construída a partir do nosso diálogo. O processo serviu como uma poderosa ferramenta de aprendizado e desenvolvimento colaborativo entre humano e IA.
