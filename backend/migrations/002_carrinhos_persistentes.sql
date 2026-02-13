-- Tabela de carrinhos persistentes
-- Mantém carrinhos de compra mesmo após redeploy

CREATE TABLE IF NOT EXISTS carrinhos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    telefone VARCHAR(20) NOT NULL,
    produto_id UUID NOT NULL,
    produto_nome VARCHAR(255) NOT NULL,
    preco_unitario DECIMAL(10, 2) NOT NULL,
    quantidade INTEGER NOT NULL DEFAULT 1,
    subtotal DECIMAL(10, 2) NOT NULL,
    criado_em TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    atualizado_em TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Índices para performance
    CONSTRAINT carrinhos_telefone_produto_key UNIQUE (telefone, produto_id)
);

-- Índice para buscar carrinhos por telefone
CREATE INDEX IF NOT EXISTS idx_carrinhos_telefone ON carrinhos(telefone);

-- Índice para limpar carrinhos antigos (>7 dias sem atualizar)
CREATE INDEX IF NOT EXISTS idx_carrinhos_atualizado ON carrinhos(atualizado_em);

-- Trigger para atualizar atualizado_em automaticamente
CREATE OR REPLACE FUNCTION update_carrinhos_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.atualizado_em = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_carrinhos_timestamp
    BEFORE UPDATE ON carrinhos
    FOR EACH ROW
    EXECUTE FUNCTION update_carrinhos_updated_at();

-- Comentários
COMMENT ON TABLE carrinhos IS 'Carrinhos de compra persistentes por telefone';
COMMENT ON COLUMN carrinhos.telefone IS 'Número de telefone do cliente (com DDI)';
COMMENT ON COLUMN carrinhos.produto_id IS 'ID do produto (UUID do Supabase)';
COMMENT ON COLUMN carrinhos.quantidade IS 'Quantidade do produto no carrinho';
COMMENT ON COLUMN carrinhos.subtotal IS 'Preço unitário × quantidade';

-- Tabela de sessões (contexto de produtos mostrados)
CREATE TABLE IF NOT EXISTS sessoes_contexto (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    telefone VARCHAR(20) NOT NULL UNIQUE,
    produtos_mostrados JSONB,
    ultima_busca TEXT,
    criado_em TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    atualizado_em TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expira_em TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '30 minutes')
);

-- Índice para buscar sessões por telefone
CREATE INDEX IF NOT EXISTS idx_sessoes_telefone ON sessoes_contexto(telefone);

-- Índice para limpar sessões expiradas
CREATE INDEX IF NOT EXISTS idx_sessoes_expira ON sessoes_contexto(expira_em);

-- Trigger para atualizar atualizado_em
CREATE OR REPLACE FUNCTION update_sessoes_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.atualizado_em = NOW();
    NEW.expira_em = NOW() + INTERVAL '30 minutes';
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_sessoes_timestamp
    BEFORE UPDATE ON sessoes_contexto
    FOR EACH ROW
    EXECUTE FUNCTION update_sessoes_updated_at();

-- Comentários
COMMENT ON TABLE sessoes_contexto IS 'Contexto temporário de sessões (produtos mostrados, etc)';
COMMENT ON COLUMN sessoes_contexto.produtos_mostrados IS 'Array JSON dos últimos produtos mostrados';
COMMENT ON COLUMN sessoes_contexto.expira_em IS 'Data de expiração (30min após última atualização)';

-- Function para limpar dados antigos (chamar via cron)
CREATE OR REPLACE FUNCTION limpar_dados_antigos()
RETURNS void AS $$
BEGIN
    -- Limpar carrinhos não atualizados há mais de 7 dias
    DELETE FROM carrinhos 
    WHERE atualizado_em < NOW() - INTERVAL '7 days';
    
    -- Limpar sessões expiradas
    DELETE FROM sessoes_contexto 
    WHERE expira_em < NOW();
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION limpar_dados_antigos IS 'Limpa carrinhos antigos (>7 dias) e sessões expiradas';
