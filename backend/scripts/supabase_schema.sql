-- ============================================================================
-- SCHEMA SUPABASE - AGENTE WHATSAPP ROÇA CAPITAL
-- ============================================================================
-- Data: 11/02/2026
-- Versão: 1.0.0
-- Descrição: Schema completo para cache/backup de produtos, pedidos e clientes
--            Sincronização bidirecional com Tiny ERP
-- ============================================================================

-- Extensões necessárias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- Para busca full-text

-- ============================================================================
-- TABELA: produtos
-- ============================================================================
-- Armazena produtos sincronizados do site/Tiny
-- Serve como cache rápido para busca do agente
-- ============================================================================

CREATE TABLE produtos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- IDs externos
    tiny_id INTEGER UNIQUE,           -- ID no Tiny ERP
    site_id VARCHAR(100),             -- ID no site (se houver)

    -- Informações básicas
    sku VARCHAR(100) NOT NULL UNIQUE,
    nome VARCHAR(255) NOT NULL,
    descricao TEXT,
    descricao_curta VARCHAR(500),

    -- Preço e estoque
    preco DECIMAL(10,2) NOT NULL,
    preco_promocional DECIMAL(10,2),
    preco_custo DECIMAL(10,2),
    estoque_atual DECIMAL(10,2) DEFAULT 0,
    estoque_minimo DECIMAL(10,2) DEFAULT 0,

    -- Peso (importante para frete)
    peso_kg DECIMAL(10,3),            -- Peso aproximado
    peso_minimo DECIMAL(10,3),        -- Para produtos variáveis
    peso_maximo DECIMAL(10,3),        -- Para produtos variáveis

    -- Variações (para produtos como queijo vendido por peso)
    requer_pesagem BOOLEAN DEFAULT FALSE,
    preco_por_kg DECIMAL(10,2),       -- Se vendido por peso
    variacoes JSONB,                  -- Array de variações [{nome, preco, peso}]

    -- Categoria e classificação
    categoria VARCHAR(100),
    categoria_id INTEGER,
    tags TEXT[],                      -- Para busca

    -- Imagens e mídia
    imagem_url VARCHAR(500),
    imagens JSONB,                    -- Array de URLs
    video_url VARCHAR(500),

    -- URLs
    url_produto VARCHAR(500),         -- Link para produto no site

    -- Metadata
    ncm VARCHAR(20),                  -- Código fiscal
    gtin VARCHAR(20),                 -- Código de barras
    unidade VARCHAR(10) DEFAULT 'UN', -- UN, KG, LT, etc

    -- SEO (do site)
    seo_title VARCHAR(255),
    seo_description TEXT,
    seo_keywords TEXT[],

    -- Status
    ativo BOOLEAN DEFAULT TRUE,
    disponivel_whatsapp BOOLEAN DEFAULT TRUE,  -- Se deve aparecer no bot

    -- Sincronização
    fonte VARCHAR(20),                -- 'tiny', 'site'
    ultima_sync_tiny TIMESTAMP,
    ultima_sync_site TIMESTAMP,

    -- Timestamps
    criado_em TIMESTAMP DEFAULT NOW(),
    atualizado_em TIMESTAMP DEFAULT NOW(),

    -- Índices para busca rápida
    CONSTRAINT produtos_sku_unique UNIQUE (sku)
);

-- Índices
CREATE INDEX idx_produtos_nome ON produtos USING gin(to_tsvector('portuguese', nome));
CREATE INDEX idx_produtos_descricao ON produtos USING gin(to_tsvector('portuguese', descricao));
CREATE INDEX idx_produtos_sku ON produtos(sku);
CREATE INDEX idx_produtos_tiny_id ON produtos(tiny_id);
CREATE INDEX idx_produtos_categoria ON produtos(categoria);
CREATE INDEX idx_produtos_ativo ON produtos(ativo) WHERE ativo = TRUE;
CREATE INDEX idx_produtos_disponivel_whatsapp ON produtos(disponivel_whatsapp) WHERE disponivel_whatsapp = TRUE;
CREATE INDEX idx_produtos_tags ON produtos USING gin(tags);

-- Full-text search combinado
CREATE INDEX idx_produtos_fulltext ON produtos USING gin(
    to_tsvector('portuguese', coalesce(nome, '') || ' ' || coalesce(descricao, '') || ' ' || coalesce(sku, ''))
);

-- ============================================================================
-- TABELA: clientes
-- ============================================================================
-- Armazena clientes que interagem via WhatsApp
-- ============================================================================

CREATE TABLE clientes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- IDs externos
    tiny_id INTEGER UNIQUE,           -- ID no Tiny

    -- Dados pessoais
    nome VARCHAR(255),
    cpf VARCHAR(14) UNIQUE,
    email VARCHAR(255),

    -- Contato
    telefone VARCHAR(20) NOT NULL UNIQUE,  -- Principal identificador
    telefone_secundario VARCHAR(20),

    -- Endereço principal
    endereco JSONB,                   -- Estrutura completa do endereço
    /*
    {
        "cep": "30000000",
        "rua": "Rua Exemplo",
        "numero": "123",
        "complemento": "Apt 101",
        "bairro": "Centro",
        "cidade": "Belo Horizonte",
        "uf": "MG",
        "pais": "Brasil"
    }
    */

    -- Histórico e estatísticas
    total_pedidos INTEGER DEFAULT 0,
    total_gasto DECIMAL(10,2) DEFAULT 0,
    ultimo_pedido_em TIMESTAMP,
    primeira_compra_em TIMESTAMP,

    -- Preferências
    produtos_favoritos UUID[],        -- IDs de produtos
    metodo_pagamento_preferido VARCHAR(50),

    -- Metadata
    notas TEXT,                       -- Observações internas
    tags TEXT[],                      -- Segmentação

    -- Timestamps
    criado_em TIMESTAMP DEFAULT NOW(),
    atualizado_em TIMESTAMP DEFAULT NOW()
);

-- Índices
CREATE INDEX idx_clientes_telefone ON clientes(telefone);
CREATE INDEX idx_clientes_cpf ON clientes(cpf);
CREATE INDEX idx_clientes_tiny_id ON clientes(tiny_id);
CREATE INDEX idx_clientes_email ON clientes(email);
CREATE INDEX idx_clientes_nome ON clientes USING gin(to_tsvector('portuguese', nome));

-- ============================================================================
-- TABELA: carrinhos
-- ============================================================================
-- Carrinhos de compra temporários (sessão por telefone)
-- ============================================================================

CREATE TABLE carrinhos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Identificação
    telefone VARCHAR(20) NOT NULL UNIQUE,  -- Um carrinho por telefone
    cliente_id UUID REFERENCES clientes(id),

    -- Items
    items JSONB NOT NULL DEFAULT '[]',
    /*
    [
        {
            "produto_id": "uuid",
            "sku": "PROD001",
            "nome": "Queijo Canastra",
            "quantidade": 2,
            "preco_unitario": 125.00,
            "peso_aproximado": 1.0,
            "requer_pesagem": true,
            "subtotal": 250.00
        }
    ]
    */

    -- Totais
    total_produtos DECIMAL(10,2) DEFAULT 0,
    frete_valor DECIMAL(10,2),
    frete_tipo VARCHAR(50),           -- 'lalamove', 'correios_sedex', etc
    frete_prazo VARCHAR(100),         -- '45 minutos', '3-5 dias úteis'
    desconto DECIMAL(10,2) DEFAULT 0,
    total_geral DECIMAL(10,2) DEFAULT 0,

    -- Status
    ativo BOOLEAN DEFAULT TRUE,

    -- Timestamps
    criado_em TIMESTAMP DEFAULT NOW(),
    atualizado_em TIMESTAMP DEFAULT NOW(),
    expira_em TIMESTAMP DEFAULT NOW() + INTERVAL '24 hours'  -- Limpa após 24h
);

-- Índices
CREATE INDEX idx_carrinhos_telefone ON carrinhos(telefone);
CREATE INDEX idx_carrinhos_ativo ON carrinhos(ativo) WHERE ativo = TRUE;
CREATE INDEX idx_carrinhos_expira_em ON carrinhos(expira_em);

-- ============================================================================
-- TABELA: pedidos
-- ============================================================================
-- TODOS os pedidos (WhatsApp, Site, Loja Física)
-- Fonte única da verdade local (sincronizado com Tiny)
-- ============================================================================

CREATE TABLE pedidos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Número único do pedido
    numero_pedido VARCHAR(50) UNIQUE NOT NULL,  -- PED-WPP-001, PED-SITE-001, etc

    -- IDs externos
    tiny_pedido_id INTEGER UNIQUE,              -- ID no Tiny ERP
    site_pedido_id VARCHAR(100),                -- ID no site (se houver)

    -- Canal de origem
    canal VARCHAR(20) NOT NULL,  -- 'whatsapp', 'site', 'loja_fisica'

    -- Cliente
    cliente_id UUID REFERENCES clientes(id),
    telefone VARCHAR(20) NOT NULL,
    cliente_nome VARCHAR(255) NOT NULL,
    cliente_cpf VARCHAR(14),
    cliente_email VARCHAR(255),

    -- Endereço de entrega
    endereco JSONB NOT NULL,

    -- Itens do pedido
    items JSONB NOT NULL,
    /*
    [
        {
            "produto_id": "uuid",
            "tiny_produto_id": 12345,
            "sku": "PROD001",
            "nome": "Queijo Canastra 1kg",
            "quantidade": 2,
            "preco_unitario": 125.00,
            "peso_real": 1.05,        // Após pesagem (se aplicável)
            "peso_cobrado": 1.0,      // Peso usado no cálculo
            "subtotal": 250.00
        }
    ]
    */

    -- Valores
    total_produtos DECIMAL(10,2) NOT NULL,
    frete_valor DECIMAL(10,2) DEFAULT 0,
    frete_tipo VARCHAR(50),
    desconto DECIMAL(10,2) DEFAULT 0,
    outras_despesas DECIMAL(10,2) DEFAULT 0,
    total DECIMAL(10,2) NOT NULL,

    -- Status do pedido
    status VARCHAR(50) NOT NULL DEFAULT 'aguardando_pagamento',
    -- Status possíveis:
    -- 'aguardando_pagamento', 'pago', 'confirmado', 'preparando',
    -- 'pronto_envio', 'enviado', 'entregue', 'cancelado'

    -- Nota Fiscal
    nf_emitida BOOLEAN DEFAULT FALSE,
    nf_numero VARCHAR(50),
    nf_chave VARCHAR(100),
    nf_url VARCHAR(500),

    -- Rastreamento
    rastreio_codigo VARCHAR(100),
    rastreio_url VARCHAR(500),
    rastreio_status VARCHAR(100),

    -- Pagamento
    pagamento_tipo VARCHAR(50) NOT NULL,  -- 'pix', 'cartao', 'dinheiro'
    pagamento_id VARCHAR(100),             -- ID Pagar.me
    pagamento_status VARCHAR(50),
    pagamento_qr_code TEXT,                -- QR Code PIX (se aplicável)
    pagamento_link VARCHAR(500),           -- Link de pagamento (cartão)

    -- Observações
    observacoes TEXT,
    observacoes_internas TEXT,

    -- Sincronização com Tiny
    tiny_sincronizado BOOLEAN DEFAULT FALSE,
    tiny_sincronizado_em TIMESTAMP,
    tiny_situacao INTEGER,                 -- Situação no Tiny (0-9)
    tiny_erro TEXT,                        -- Erro de sincronização (se houver)

    -- Timestamps
    criado_em TIMESTAMP DEFAULT NOW(),
    atualizado_em TIMESTAMP DEFAULT NOW(),
    pago_em TIMESTAMP,
    confirmado_em TIMESTAMP,
    enviado_em TIMESTAMP,
    entregue_em TIMESTAMP,
    cancelado_em TIMESTAMP
);

-- Índices
CREATE INDEX idx_pedidos_numero ON pedidos(numero_pedido);
CREATE INDEX idx_pedidos_telefone ON pedidos(telefone);
CREATE INDEX idx_pedidos_cpf ON pedidos(cliente_cpf);
CREATE INDEX idx_pedidos_tiny_id ON pedidos(tiny_pedido_id);
CREATE INDEX idx_pedidos_canal ON pedidos(canal);
CREATE INDEX idx_pedidos_status ON pedidos(status);
CREATE INDEX idx_pedidos_criado_em ON pedidos(criado_em DESC);
CREATE INDEX idx_pedidos_cliente_id ON pedidos(cliente_id);
CREATE INDEX idx_pedidos_tiny_sync ON pedidos(tiny_sincronizado) WHERE tiny_sincronizado = FALSE;

-- ============================================================================
-- TABELA: sessoes
-- ============================================================================
-- Sessões de atendimento (controle humano-agente)
-- ============================================================================

CREATE TABLE sessoes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    telefone VARCHAR(20) NOT NULL UNIQUE,
    cliente_id UUID REFERENCES clientes(id),

    -- Modo de atendimento
    modo VARCHAR(20) NOT NULL DEFAULT 'agent',  -- 'agent', 'human', 'paused'

    -- Atendente humano
    atendente_humano VARCHAR(255),
    atendente_assumiu_em TIMESTAMP,

    -- Timestamps de mensagens
    ultima_msg_cliente TIMESTAMP,
    ultima_msg_agente TIMESTAMP,
    ultima_msg_humano TIMESTAMP,

    -- Pausado
    pausado_em TIMESTAMP,
    pausado_por VARCHAR(255),

    -- Metadata
    metadata JSONB DEFAULT '{}',

    -- Timestamps
    criado_em TIMESTAMP DEFAULT NOW(),
    atualizado_em TIMESTAMP DEFAULT NOW()
);

-- Índices
CREATE INDEX idx_sessoes_telefone ON sessoes(telefone);
CREATE INDEX idx_sessoes_modo ON sessoes(modo);
CREATE INDEX idx_sessoes_atendente ON sessoes(atendente_humano);

-- ============================================================================
-- TABELA: mensagens
-- ============================================================================
-- Histórico de mensagens (para memória de conversa)
-- ============================================================================

CREATE TABLE mensagens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    sessao_id UUID REFERENCES sessoes(id) ON DELETE CASCADE,
    telefone VARCHAR(20) NOT NULL,

    -- Mensagem
    mensagem TEXT NOT NULL,
    origem VARCHAR(20) NOT NULL,  -- 'customer', 'agent', 'human', 'system'

    -- Metadata
    metadata JSONB DEFAULT '{}',

    -- Timestamp
    criado_em TIMESTAMP DEFAULT NOW()
);

-- Índices
CREATE INDEX idx_mensagens_sessao_id ON mensagens(sessao_id);
CREATE INDEX idx_mensagens_telefone ON mensagens(telefone);
CREATE INDEX idx_mensagens_origem ON mensagens(origem);
CREATE INDEX idx_mensagens_criado_em ON mensagens(criado_em DESC);

-- ============================================================================
-- TABELA: sync_log
-- ============================================================================
-- Log de sincronizações com Tiny (auditoria)
-- ============================================================================

CREATE TABLE sync_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Operação
    operacao VARCHAR(100) NOT NULL,  -- 'sync_produtos', 'sync_pedido', 'create_cliente', etc
    entidade VARCHAR(50) NOT NULL,   -- 'produto', 'pedido', 'cliente'

    -- IDs
    entidade_id UUID,                -- ID local (UUID)
    tiny_id INTEGER,                 -- ID no Tiny

    -- Status
    status VARCHAR(20) NOT NULL,     -- 'success', 'error', 'pending'
    mensagem TEXT,
    erro TEXT,

    -- Dados
    dados JSONB,                     -- Dados enviados/recebidos

    -- Tentativas
    tentativas INTEGER DEFAULT 1,
    proxima_tentativa TIMESTAMP,

    -- Timestamp
    criado_em TIMESTAMP DEFAULT NOW(),
    atualizado_em TIMESTAMP DEFAULT NOW()
);

-- Índices
CREATE INDEX idx_sync_log_operacao ON sync_log(operacao);
CREATE INDEX idx_sync_log_entidade ON sync_log(entidade);
CREATE INDEX idx_sync_log_status ON sync_log(status);
CREATE INDEX idx_sync_log_criado_em ON sync_log(criado_em DESC);
CREATE INDEX idx_sync_log_pending ON sync_log(status, proxima_tentativa) WHERE status = 'pending';

-- ============================================================================
-- TRIGGERS - Atualizar updated_at automaticamente
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.atualizado_em = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_produtos_updated_at BEFORE UPDATE ON produtos
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_clientes_updated_at BEFORE UPDATE ON clientes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_carrinhos_updated_at BEFORE UPDATE ON carrinhos
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_pedidos_updated_at BEFORE UPDATE ON pedidos
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sessoes_updated_at BEFORE UPDATE ON sessoes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- FUNÇÕES ÚTEIS
-- ============================================================================

-- Função para gerar número de pedido
CREATE OR REPLACE FUNCTION generate_order_number(canal_origem VARCHAR)
RETURNS VARCHAR AS $$
DECLARE
    prefixo VARCHAR;
    contador INTEGER;
    numero VARCHAR;
BEGIN
    -- Definir prefixo baseado no canal
    CASE canal_origem
        WHEN 'whatsapp' THEN prefixo := 'WPP';
        WHEN 'site' THEN prefixo := 'SITE';
        WHEN 'loja_fisica' THEN prefixo := 'LOJA';
        ELSE prefixo := 'PED';
    END CASE;

    -- Buscar último contador
    SELECT COUNT(*) + 1 INTO contador
    FROM pedidos
    WHERE canal = canal_origem
    AND DATE(criado_em) = CURRENT_DATE;

    -- Formatar: PED-WPP-YYYYMMDD-0001
    numero := 'PED-' || prefixo || '-' || TO_CHAR(NOW(), 'YYYYMMDD') || '-' || LPAD(contador::TEXT, 4, '0');

    RETURN numero;
END;
$$ LANGUAGE plpgsql;

-- Função para buscar produtos (full-text search)
CREATE OR REPLACE FUNCTION buscar_produtos(termo_busca TEXT, limite INT DEFAULT 20)
RETURNS TABLE (
    id UUID,
    sku VARCHAR,
    nome VARCHAR,
    descricao TEXT,
    preco DECIMAL,
    estoque_atual DECIMAL,
    imagem_url VARCHAR,
    relevancia REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.id,
        p.sku,
        p.nome,
        p.descricao,
        p.preco,
        p.estoque_atual,
        p.imagem_url,
        ts_rank(
            to_tsvector('portuguese', COALESCE(p.nome, '') || ' ' || COALESCE(p.descricao, '')),
            plainto_tsquery('portuguese', termo_busca)
        ) AS relevancia
    FROM produtos p
    WHERE
        p.ativo = TRUE
        AND p.disponivel_whatsapp = TRUE
        AND (
            to_tsvector('portuguese', COALESCE(p.nome, '') || ' ' || COALESCE(p.descricao, ''))
            @@ plainto_tsquery('portuguese', termo_busca)
            OR p.sku ILIKE '%' || termo_busca || '%'
        )
    ORDER BY relevancia DESC, p.nome
    LIMIT limite;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- VIEWS ÚTEIS
-- ============================================================================

-- View: Pedidos com informações do cliente
CREATE OR REPLACE VIEW vw_pedidos_completos AS
SELECT
    p.*,
    c.nome AS cliente_nome_completo,
    c.email AS cliente_email_completo,
    c.total_pedidos AS cliente_total_pedidos,
    s.modo AS sessao_modo,
    s.atendente_humano
FROM pedidos p
LEFT JOIN clientes c ON p.cliente_id = c.id
LEFT JOIN sessoes s ON p.telefone = s.telefone;

-- View: Estatísticas de sincronização
CREATE OR REPLACE VIEW vw_sync_stats AS
SELECT
    DATE(criado_em) AS data,
    operacao,
    status,
    COUNT(*) AS quantidade
FROM sync_log
WHERE criado_em >= NOW() - INTERVAL '30 days'
GROUP BY DATE(criado_em), operacao, status
ORDER BY data DESC, operacao;

-- ============================================================================
-- POLICIES (Row Level Security - opcional)
-- ============================================================================
-- Descomentar se quiser usar RLS

-- ALTER TABLE produtos ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE clientes ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE pedidos ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE sessoes ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE mensagens ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- FIM DO SCHEMA
-- ============================================================================

-- Comentários nas tabelas
COMMENT ON TABLE produtos IS 'Cache de produtos sincronizados do Tiny/Site';
COMMENT ON TABLE clientes IS 'Clientes que interagem via WhatsApp';
COMMENT ON TABLE carrinhos IS 'Carrinhos de compra temporários';
COMMENT ON TABLE pedidos IS 'Todos os pedidos (WhatsApp + Site + Loja)';
COMMENT ON TABLE sessoes IS 'Sessões de atendimento (controle humano-agente)';
COMMENT ON TABLE mensagens IS 'Histórico de mensagens (memória de conversa)';
COMMENT ON TABLE sync_log IS 'Log de sincronizações com Tiny ERP';

-- Mensagem de conclusão
DO $$
BEGIN
    RAISE NOTICE '✅ Schema Supabase criado com sucesso!';
    RAISE NOTICE '📊 Tabelas: produtos, clientes, carrinhos, pedidos, sessoes, mensagens, sync_log';
    RAISE NOTICE '🔍 Funções: generate_order_number, buscar_produtos';
    RAISE NOTICE '📈 Views: vw_pedidos_completos, vw_sync_stats';
END $$;
