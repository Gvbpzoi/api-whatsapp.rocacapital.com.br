-- =====================================================
-- SETUP COMPLETO DO BANCO - ROÇA CAPITAL WHATSAPP AGENT
-- =====================================================
-- Execute este SQL no Supabase SQL Editor
-- =====================================================

-- ====== TABELA: produtos_site ======
-- Produtos do site, sincronizados com Tiny ERP
CREATE TABLE IF NOT EXISTS produtos_site (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tiny_id text UNIQUE,
    nome text NOT NULL,
    descricao text,
    preco numeric(10,2),
    preco_promocional numeric(10,2),
    peso text,
    unidade text,
    imagem_url text,
    imagens_adicionais jsonb,
    link_produto text,
    categoria text,
    subcategoria text,
    tags text[],
    estoque_disponivel boolean DEFAULT true,
    quantidade_estoque integer DEFAULT 0,
    ativo boolean DEFAULT true,
    destaque boolean DEFAULT false,
    sincronizado_em timestamp DEFAULT now(),
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now()
);

-- Índices para produtos_site
CREATE INDEX IF NOT EXISTS idx_produtos_site_categoria ON produtos_site(categoria);
CREATE INDEX IF NOT EXISTS idx_produtos_site_ativo ON produtos_site(ativo);
CREATE INDEX IF NOT EXISTS idx_produtos_site_tiny_id ON produtos_site(tiny_id);
CREATE INDEX IF NOT EXISTS idx_produtos_site_nome ON produtos_site USING gin(to_tsvector('portuguese', nome));

COMMENT ON TABLE produtos_site IS 'Produtos do site, sincronizados com Tiny ERP';
COMMENT ON COLUMN produtos_site.tiny_id IS 'ID do produto no Tiny ERP';
COMMENT ON COLUMN produtos_site.sincronizado_em IS 'Última vez que foi sincronizado com Tiny';

-- ====== TABELA: pedidos ======
-- Pedidos criados via WhatsApp
CREATE TABLE IF NOT EXISTS pedidos (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    numero_pedido text UNIQUE,
    phone text NOT NULL,
    nome_cliente text,
    email_cliente text,
    endereco jsonb,
    items jsonb NOT NULL,
    subtotal numeric(10,2) NOT NULL,
    frete numeric(10,2) DEFAULT 0,
    desconto numeric(10,2) DEFAULT 0,
    total numeric(10,2) NOT NULL,
    status text NOT NULL DEFAULT 'carrinho',
    tiny_pedido_id text,
    link_pagamento text,
    observacoes text,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now()
);

-- Índices para pedidos
CREATE INDEX IF NOT EXISTS idx_pedidos_phone ON pedidos(phone);
CREATE INDEX IF NOT EXISTS idx_pedidos_status ON pedidos(status);
CREATE INDEX IF NOT EXISTS idx_pedidos_tiny_id ON pedidos(tiny_pedido_id);
CREATE INDEX IF NOT EXISTS idx_pedidos_numero ON pedidos(numero_pedido);
CREATE INDEX IF NOT EXISTS idx_pedidos_created_at ON pedidos(created_at DESC);

COMMENT ON TABLE pedidos IS 'Pedidos criados via WhatsApp';
COMMENT ON COLUMN pedidos.status IS 'Status: carrinho, aguardando_pagamento, pago, processando, enviado, entregue, cancelado';
COMMENT ON COLUMN pedidos.tiny_pedido_id IS 'ID do pedido criado no Tiny ERP';
COMMENT ON COLUMN pedidos.items IS 'Array de produtos: [{produto_id, nome, quantidade, preco}]';

-- ====== TABELA: pagamentos ======
-- Pagamentos dos pedidos
CREATE TABLE IF NOT EXISTS pagamentos (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pedido_id uuid REFERENCES pedidos(id) ON DELETE CASCADE,
    status text NOT NULL DEFAULT 'pendente',
    valor numeric(10,2) NOT NULL,
    metodo text,
    gateway text,
    gateway_id text,
    gateway_response jsonb,
    confirmado_em timestamp,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now()
);

-- Índices para pagamentos
CREATE INDEX IF NOT EXISTS idx_pagamentos_pedido_id ON pagamentos(pedido_id);
CREATE INDEX IF NOT EXISTS idx_pagamentos_status ON pagamentos(status);
CREATE INDEX IF NOT EXISTS idx_pagamentos_gateway_id ON pagamentos(gateway_id);

COMMENT ON TABLE pagamentos IS 'Pagamentos dos pedidos';
COMMENT ON COLUMN pagamentos.status IS 'Status: pendente, processando, aprovado, recusado, cancelado, estornado';
COMMENT ON COLUMN pagamentos.gateway IS 'Gateway: pix, mercadopago, pagseguro, etc';

-- ====== TABELA: rastreios ======
-- Rastreamento de entregas
CREATE TABLE IF NOT EXISTS rastreios (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pedido_id uuid REFERENCES pedidos(id) ON DELETE CASCADE,
    codigo_rastreio text NOT NULL,
    transportadora text,
    status text,
    ultima_atualizacao timestamp,
    historico jsonb,
    notificado boolean DEFAULT false,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now()
);

-- Índices para rastreios
CREATE INDEX IF NOT EXISTS idx_rastreios_pedido_id ON rastreios(pedido_id);
CREATE INDEX IF NOT EXISTS idx_rastreios_codigo ON rastreios(codigo_rastreio);
CREATE INDEX IF NOT EXISTS idx_rastreios_notificado ON rastreios(notificado);

COMMENT ON TABLE rastreios IS 'Rastreamento de entregas';
COMMENT ON COLUMN rastreios.historico IS 'Histórico de eventos: [{data, status, local, descricao}]';
COMMENT ON COLUMN rastreios.notificado IS 'Se cliente já foi notificado deste status';

-- ====== TABELA: sessoes_conversa ======
-- Sessões de conversa do WhatsApp (histórico e contexto)
CREATE TABLE IF NOT EXISTS sessoes_conversa (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    phone text NOT NULL,
    historico jsonb,
    contexto jsonb,
    ultima_mensagem timestamp,
    ativa boolean DEFAULT true,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now()
);

-- Índices para sessoes_conversa
CREATE INDEX IF NOT EXISTS idx_sessoes_phone ON sessoes_conversa(phone);
CREATE INDEX IF NOT EXISTS idx_sessoes_ativa ON sessoes_conversa(ativa);

COMMENT ON TABLE sessoes_conversa IS 'Sessões de conversa do WhatsApp';
COMMENT ON COLUMN sessoes_conversa.historico IS 'Histórico de mensagens: [{role, content, timestamp}]';
COMMENT ON COLUMN sessoes_conversa.contexto IS 'Contexto da conversa: {carrinho, preferencias, nome_cliente, etc}';

-- =====================================================
-- VIEWS ÚTEIS
-- =====================================================

-- View: pedidos_com_pagamento
CREATE OR REPLACE VIEW pedidos_com_pagamento AS
SELECT
    p.*,
    pg.status as status_pagamento,
    pg.metodo as metodo_pagamento,
    pg.gateway as gateway_pagamento,
    pg.confirmado_em as pago_em
FROM pedidos p
LEFT JOIN pagamentos pg ON pg.pedido_id = p.id;

-- View: produtos_disponiveis
CREATE OR REPLACE VIEW produtos_disponiveis AS
SELECT *
FROM produtos_site
WHERE ativo = true
  AND estoque_disponivel = true
ORDER BY categoria, nome;

-- =====================================================
-- FUNCTIONS ÚTEIS
-- =====================================================

-- Function: atualizar_updated_at
CREATE OR REPLACE FUNCTION atualizar_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers para atualizar updated_at automaticamente
CREATE TRIGGER trigger_produtos_site_updated_at
    BEFORE UPDATE ON produtos_site
    FOR EACH ROW
    EXECUTE FUNCTION atualizar_updated_at();

CREATE TRIGGER trigger_pedidos_updated_at
    BEFORE UPDATE ON pedidos
    FOR EACH ROW
    EXECUTE FUNCTION atualizar_updated_at();

CREATE TRIGGER trigger_pagamentos_updated_at
    BEFORE UPDATE ON pagamentos
    FOR EACH ROW
    EXECUTE FUNCTION atualizar_updated_at();

CREATE TRIGGER trigger_rastreios_updated_at
    BEFORE UPDATE ON rastreios
    FOR EACH ROW
    EXECUTE FUNCTION atualizar_updated_at();

-- =====================================================
-- DADOS DE EXEMPLO (OPCIONAL - DESCOMENTE PARA TESTAR)
-- =====================================================

/*
-- Produto de exemplo
INSERT INTO produtos_site (
    nome, descricao, preco, categoria, subcategoria,
    estoque_disponivel, quantidade_estoque, ativo
) VALUES (
    'Queijo Canastra Meia Cura 500g',
    'Queijo artesanal da Serra da Canastra, maturado por 21 dias',
    45.00,
    'queijo',
    'canastra',
    true,
    50,
    true
) ON CONFLICT DO NOTHING;
*/

-- =====================================================
-- FIM DO SETUP
-- =====================================================

SELECT 'Setup concluído com sucesso!' as status;
