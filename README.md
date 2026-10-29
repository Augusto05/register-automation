# 🤖 Automação RPA de Cadastro de Leads - Salesforce C6 Bank (24/7)

Sistema autônomo em Python com Playwright para cadastro contínuo de leads no portal Salesforce do C6 Bank, alimentado por planilha online pública no Google Sheets e monitorado em tempo real via **Dashboard Streamlit**.

Repositório GitHub: **https://github.com/Augusto05/register-automation**

---

## ⚡ Como Iniciar em 1 Clique (Para Usuários Finais)

Para quem for rodar ou acompanhar na máquina remota, **não precisa de conhecimentos técnicos**:

### No Windows:
Basta dar **duplo clique** no arquivo:
👉 **`INICIAR_TUDO.bat`**

O que ele faz automaticamente:
1. Configura o ambiente e dependências;
2. Valida a assinatura do escritório na **LeadSale** (usando o token `lri_...` salvo em `leadsale_token.txt` ou configurado no botão **🔑 Configurar Token** do painel);
3. Abre a janela do **Dashboard Streamlit** no navegador para acompanhar o progresso;
4. Abre o **Google Chrome** diretamente na página de Leads do C6 Bank;
5. Se for a primeira vez, a pessoa apenas digita seu login/senha e 2FA uma única vez;
6. O robô detecta o login e inicia o processamento 24 horas por dia!

---

## 🔐 Validação de Assinatura na LeadSale (`leadsale_token.txt`)

O robô só opera em escritórios com assinatura ativa na **LeadSale** (`https://leadsale.com.br/api/robo_indicacao/status`), conferindo a liberação ao abrir e depois 1 vez por dia.

1. **Onde guardar o Token**:
   - Você pode clicar no botão **`🔑 Configurar Token`** dentro do Painel de Controle e colar sua chave `lri_...`, **ou** criar um arquivo de texto chamado `leadsale_token.txt` na pasta do robô contendo apenas o token do escritório.
2. **Três cuidados importantes**:
   - **Não pergunte mais de uma vez por hora com token errado**: Erros seguidos de token bloqueiam a internet do escritório por 1 hora.
   - **Liberação de Internet (IP)**: Se aparecer `"Robô não liberado para este escritório. Fale com a LeadSale."` logo na primeira vez, avise a LeadSale — ela vê na hora qual internet tentou e libera com um clique.
   - **Sigilo do Token**: O token é uma senha confidencial. Não envie em grupos e nunca o comite no Git (`leadsale_token.txt` já está protegido no `.gitignore` e oculto nos logs e na tela).

### No Mac / Linux:
Abra o terminal na pasta e execute:
```bash
./INICIAR_TUDO.sh
```

---

## ☁️ Como Acompanhar Online no Streamlit Cloud (Celular/PC)

O projeto já está preparado para o **Streamlit Community Cloud** gratuito:

1. Acesse [share.streamlit.io](https://share.streamlit.io) e conecte com sua conta GitHub (**Augusto05**);
2. Clique em **"Create app"**;
3. Selecione o repositório: `Augusto05/register-automation`;
4. Branch: `main`;
5. Main file path: `dashboard.py`;
6. Clique em **"Deploy"**!

Você terá um link público seguro (ex: `https://c6-leads-monitor.streamlit.app`) para acompanhar o robô pelo celular a qualquer hora!

---

## 📋 Formato da Planilha Online (Google Sheets)

A planilha deve ser configurada como **"Qualquer pessoa com o link pode visualizar"**. 
Os cabeçalhos recomendados na primeira linha são:

| CNPJ | Razão Social | Email | Telefone | Status | Obs |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `12.345.678/0001-99` | Alpha Servicos Digitais Ltda | contato@alphaservicos.com.br | `(11) 98765-4321` | *(vazio)* | *(vazio)* |

* O ID da planilha fica na URL: `https://docs.google.com/spreadsheets/d/`**`SEU_ID_AQUI`**`/edit`.
* Insira esse ID no arquivo `config.py` na variável `SPREADSHEET_ID`.

*(Opcional)* Se quiser que o robô atualize a coluna **Status** para `CADASTRADO` ou `INDISPONÍVEL` diretamente no Google Sheets:
1. Na sua planilha, vá em **Extensões** > **Apps Script**;
2. Cole o código que está em [google_apps_script.js](file:///Users/bueno/coding/leadsale/register-automation/google_apps_script.js);
3. Clique em **Implantar** > **Nova implantação** > **App da Web** > Quem tem acesso: **Qualquer pessoa**;
4. Cole a URL gerada em `APPS_SCRIPT_WEBHOOK_URL` no `config.py`.

---

## 🛡️ Regras de Negócio e Segurança

1. **CNPJ**: Converte automaticamente para apenas números sem pontuação (exigência do portal C6).
2. **Telefone**: Valida 11 dígitos (DDD + 9) e adiciona o prefixo `55` (ex: `5511999998888`).
3. **Razão Social**: Preenche o campo oficial e divide em *Primeiro Nome* e *Sobrenome* (obrigatório no Salesforce).
4. **Intervalo de 3 Minutos**: Aguarda 180s (± 10s aleatórios) entre leads consecutivos com fila acumulada.
5. **Anti-Logoff**: Durante ociosidade (sem leads novos), faz uma interação periódica a cada 4 minutos para a sessão nunca expirar.
6. **Deduplicação**: Banco SQLite local (`leads_history.db`) impede qualquer tentativa de reenviar um CNPJ já processado.
