# ⚡ Início Rápido - Agente WhatsApp

Comece a usar o sistema em **5 minutos**!

## 🎯 Passo a Passo

### 1️⃣ Configurar Ambiente (1min)

```bash
# Clonar/acessar o projeto
cd agente-whatsapp

# Copiar configuração
cp backend/.env.example backend/.env

# Editar com suas chaves
nano backend/.env
```

**Mínimo necessário no .env:**
```bash
OPENAI_API_KEY=sk-sua-chave-aqui
DATABASE_URL=postgresql://agente:agente123@postgres:5432/agente_whatsapp
REDIS_URL=redis://redis:6379/0
```

### 2️⃣ Subir o Sistema (2min)

```bash
cd backend

# Subir tudo (backend + banco + redis)
docker-compose up -d

# Ver logs
docker-compose logs -f backend
```

**Pronto! 🎉** Serviços rodando:
- Backend: http://localhost:8000
- Docs: http://localhost:8000/docs
- n8n: http://localhost:5678

### 3️⃣ Testar (2min)

```bash
# 1. Health check
curl http://localhost:8000/

# 2. Simular mensagem de cliente
curl -X POST http://localhost:8000/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "5531999999999",
    "message": "Oi, quero queijo",
    "sender_type": "customer"
  }'

# 3. Ver status da sessão
curl http://localhost:8000/session/5531999999999/status | jq

# 4. Assumir conversa (você)
curl -X POST "http://localhost:8000/session/5531999999999/takeover?attendant_id=seu@email.com"

# 5. Cliente manda outra (bot NÃO responde)
curl -X POST http://localhost:8000/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "5531999999999",
    "message": "Tem desconto?",
    "sender_type": "customer"
  }'

# 6. Liberar de volta
curl -X POST http://localhost:8000/session/5531999999999/release
```

### 4️⃣ Integrar com WhatsApp

#### Opção A: Via n8n (Recomendado)

1. Acesse http://localhost:5678
2. Login: `admin` / `admin123`
3. Import: `n8n/webhook_whatsapp_simples.json`
4. Configure webhook do WhatsApp Business API para apontar para n8n
5. Done! ✅

#### Opção B: Direto na API

Configure webhook do WhatsApp para:
```
POST http://seu-servidor.com:8000/webhook/whatsapp
```

---

## 🎮 Comandos Essenciais

### No WhatsApp (como atendente):

```
/pausar    → Pausa o bot
/retomar   → Bot volta a responder
/assumir   → Você assume explicitamente
/liberar   → Libera para o bot
/status    → Ver status da conversa
```

### Via API:

```bash
# Assumir conversa
curl -X POST http://localhost:8000/session/{phone}/takeover \
  -d '{"attendant_id": "seu@email.com"}'

# Liberar conversa
curl -X POST http://localhost:8000/session/{phone}/release

# Ver status
curl http://localhost:8000/session/{phone}/status

# Listar conversas ativas
curl http://localhost:8000/sessions/active
```

---

## 📊 Verificar se está funcionando

### 1. Backend rodando?
```bash
curl http://localhost:8000/
# Deve retornar: {"status": "online", ...}
```

### 2. Banco conectado?
```bash
docker-compose exec postgres psql -U agente -d agente_whatsapp -c "\dt"
# Deve mostrar tabelas
```

### 3. Redis rodando?
```bash
docker-compose exec redis redis-cli ping
# Deve retornar: PONG
```

### 4. Logs ok?
```bash
docker-compose logs backend | grep ERROR
# Não deve ter erros críticos
```

---

## 🐛 Troubleshooting Rápido

### Backend não sobe

```bash
# Ver logs detalhados
docker-compose logs backend

# Verificar portas
lsof -i :8000

# Reiniciar
docker-compose restart backend
```

### Erro de conexão com banco

```bash
# Verificar se banco está rodando
docker-compose ps

# Ver logs do postgres
docker-compose logs postgres

# Recrear banco
docker-compose down -v
docker-compose up -d
```

### Comandos não funcionam

```bash
# Verificar formato do JSON
curl -X POST http://localhost:8000/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -d '{"phone": "5531999999999", "message": "/status", "sender_type": "customer"}' \
  | jq
```

---

## 📚 Próximos Passos

Agora que está funcionando:

1. **Leia a documentação completa**: [README.md](README.md)
2. **Configure integrações**: [docs/EXEMPLOS_USO.md](docs/EXEMPLOS_USO.md)
3. **Entenda os comandos**: [docs/GUIA_COMANDOS.md](docs/GUIA_COMANDOS.md)
4. **Implemente o agente IA**: Ver TODOs no código
5. **Deploy em produção**: Ver seção Deploy no README

---

## 🆘 Precisa de Ajuda?

- 📖 **Docs completas**: [README.md](README.md)
- 💡 **Exemplos**: [docs/EXEMPLOS_USO.md](docs/EXEMPLOS_USO.md)
- 🐛 **Issues**: GitHub Issues
- 📧 **Email**: dev@rocacapital.com.br

---

**Dica:** Use o Swagger Docs em http://localhost:8000/docs para testar os endpoints visualmente!
