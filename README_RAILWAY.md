**Deploy na Railway**

- Detecta Python via `requirements.txt` e usa `Procfile` com `web: python script.py`.
- O Flask expõe o mini app (inclui `/webapp`, `/pagamento-aprovado` e `/health`).
- O bot roda em modo polling (não precisa webhook). Isso é suficiente na Railway.

**Variáveis de ambiente na Railway**
- `BOT_TOKEN` (obrigatório): token do bot do Telegram.
- `WEBAPP_BASE_URL` (recomendado): URL pública HTTPS do app na Railway, por exemplo `https://<seu-subdominio>.up.railway.app` — isso habilita os botões do Telegram a abrirem como mini app.
- `PORT` (opcional): a Railway define automaticamente; o Flask já lê `PORT` do ambiente.
- `USE_NGROK=false` na Railway (padrão).

**Passos**
1. Faça o push do repositório para o GitHub.
2. Na Railway, crie um novo projeto a partir do repositório do GitHub.
3. Em Variables, adicione:
   - `BOT_TOKEN=XXXXXXXXXXXXXXXXXXXXXXXX`
   - `WEBAPP_BASE_URL=https://<dominio>.up.railway.app`
4. Deploy. Aguarde a URL pública ficar ativa.
5. No Telegram, envie `/start` ao bot para testar.

**Notas**
- Sem `WEBAPP_BASE_URL` HTTPS, os botões funcionam como links normais (sem mini app).
- Com `WEBAPP_BASE_URL` HTTPS, os botões usam WebApp (mini app) e o fluxo de `sendData` funciona.
- A página `pagina_obrigado.html` é independente; hospede-a no seu domínio HTTPS e configure o checkout para redirecionar para ela.
