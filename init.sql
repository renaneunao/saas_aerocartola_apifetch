-- Arquivo de inicialização do banco de dados
-- Todas as tabelas são criadas aqui na ordem correta (respeitando foreign keys)

-- Tabelas base (sem dependências)
CREATE TABLE IF NOT EXISTS acf_clubes (
    id INTEGER PRIMARY KEY,
    nome TEXT,
    abreviacao TEXT,
    slug TEXT,
    apelido TEXT,
    nome_fantasia TEXT,
    url_editoria TEXT
);

CREATE TABLE IF NOT EXISTS acf_posicoes (
    id INTEGER PRIMARY KEY,
    nome TEXT,
    abreviacao TEXT
);

CREATE TABLE IF NOT EXISTS acf_status (
    id INTEGER PRIMARY KEY,
    nome TEXT
);

CREATE TABLE IF NOT EXISTS acf_credenciais (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    env_key TEXT UNIQUE,
    access_token TEXT,
    refresh_token TEXT,
    id_token TEXT,
    estrategia INTEGER DEFAULT 1,
    essential_cookies TEXT
);

CREATE TABLE IF NOT EXISTS acf_esquemas (
    esquema_id INTEGER PRIMARY KEY,
    nome TEXT,
    ata INTEGER,
    gol INTEGER,
    lat INTEGER,
    mei INTEGER,
    tec INTEGER,
    zag INTEGER
);

-- Tabelas que dependem de clubes, posicoes, status
CREATE TABLE IF NOT EXISTS acf_atletas (
    atleta_id INTEGER PRIMARY KEY,
    rodada_id INTEGER,  -- Apenas para referência, não parte da chave
    clube_id INTEGER,
    posicao_id INTEGER,
    status_id INTEGER,
    pontos_num REAL,
    media_num REAL,
    variacao_num REAL,
    preco_num REAL,
    jogos_num INTEGER,
    entrou_em_campo BOOLEAN,
    slug TEXT,
    apelido TEXT,
    nome TEXT,
    foto TEXT,
    temporada INTEGER,  -- Temporada do campeonato (ex: 2025)
    FOREIGN KEY (clube_id) REFERENCES acf_clubes(id),
    FOREIGN KEY (posicao_id) REFERENCES acf_posicoes(id),
    FOREIGN KEY (status_id) REFERENCES acf_status(id)
);

-- Tabelas que dependem de clubes
CREATE TABLE IF NOT EXISTS acf_partidas (
    partida_id INTEGER PRIMARY KEY,
    rodada_id INTEGER,
    clube_casa_id INTEGER,
    clube_visitante_id INTEGER,
    placar_oficial_mandante INTEGER,
    placar_oficial_visitante INTEGER,
    local TEXT,
    partida_data TEXT,
    valida BOOLEAN,
    timestamp INTEGER,
    temporada INTEGER,  -- Temporada do campeonato (ex: 2025)
    FOREIGN KEY (clube_casa_id) REFERENCES acf_clubes(id),
    FOREIGN KEY (clube_visitante_id) REFERENCES acf_clubes(id)
);

CREATE TABLE IF NOT EXISTS acf_pontuados (
    atleta_id INTEGER,
    rodada_id INTEGER,
    clube_id INTEGER,
    posicao_id INTEGER,
    pontuacao REAL,
    entrou_em_campo BOOLEAN,
    apelido TEXT,
    foto TEXT,
    scout_a INTEGER DEFAULT 0,  -- Assistência
    scout_ca INTEGER DEFAULT 0, -- Cartão Amarelo
    scout_cv INTEGER DEFAULT 0, -- Cartão Vermelho
    scout_de INTEGER DEFAULT 0, -- Defesa
    scout_ds INTEGER DEFAULT 0, -- Desarme
    scout_fc INTEGER DEFAULT 0, -- Falta Cometida
    scout_fd INTEGER DEFAULT 0, -- Finalização Defendida
    scout_ff INTEGER DEFAULT 0, -- Finalização Fora
    scout_fs INTEGER DEFAULT 0, -- Falta Sofrida
    scout_g INTEGER DEFAULT 0,  -- Gol
    scout_gs INTEGER DEFAULT 0, -- Gol Sofrido
    scout_i INTEGER DEFAULT 0,  -- Impedimento
    scout_sg INTEGER DEFAULT 0, -- Sem Gol
    temporada INTEGER,  -- Temporada do campeonato (ex: 2025)
    PRIMARY KEY (atleta_id, rodada_id),
    FOREIGN KEY (clube_id) REFERENCES acf_clubes(id),
    FOREIGN KEY (posicao_id) REFERENCES acf_posicoes(id)
);

CREATE TABLE IF NOT EXISTS acf_destaques (
    atleta_id INTEGER PRIMARY KEY,
    posicao TEXT,
    posicao_abreviacao TEXT,
    clube_id INTEGER,
    clube TEXT,
    apelido TEXT,
    preco_editorial REAL,
    escalacoes INTEGER,
    FOREIGN KEY (clube_id) REFERENCES acf_clubes(id)
);

-- Tabelas que dependem de atletas
CREATE TABLE IF NOT EXISTS acf_gato_mestre (
    atleta_id INTEGER PRIMARY KEY,
    minimo_para_valorizar REAL,
    minutos_jogados INTEGER,
    FOREIGN KEY (atleta_id) REFERENCES acf_atletas(atleta_id)
);

-- Tabelas históricas (para manter histórico de dados por rodada)
CREATE TABLE IF NOT EXISTS acf_atletas_historico (
    atleta_id INTEGER,
    rodada_id INTEGER,
    clube_id INTEGER,
    posicao_id INTEGER,
    status_id INTEGER,
    preco_num REAL,
    media_num REAL,
    variacao_num REAL,
    pontos_num REAL,
    jogos_num INTEGER,
    entrou_em_campo BOOLEAN,
    slug TEXT,
    apelido TEXT,
    nome TEXT,
    foto TEXT,
    temporada INTEGER,  -- Temporada do campeonato (ex: 2025)
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (atleta_id, rodada_id),
    FOREIGN KEY (clube_id) REFERENCES acf_clubes(id),
    FOREIGN KEY (posicao_id) REFERENCES acf_posicoes(id),
    FOREIGN KEY (status_id) REFERENCES acf_status(id)
);

CREATE INDEX IF NOT EXISTS idx_atletas_historico_rodada ON acf_atletas_historico(rodada_id);
CREATE INDEX IF NOT EXISTS idx_atletas_historico_clube ON acf_atletas_historico(clube_id);

CREATE TABLE IF NOT EXISTS acf_destaques_historico (
    atleta_id INTEGER,
    rodada_id INTEGER,
    escalacoes INTEGER,
    preco_editorial REAL,
    posicao TEXT,
    posicao_abreviacao TEXT,
    clube_id INTEGER,
    clube TEXT,
    apelido TEXT,
    temporada INTEGER,  -- Temporada do campeonato (ex: 2025)
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (atleta_id, rodada_id),
    FOREIGN KEY (clube_id) REFERENCES acf_clubes(id)
);

CREATE INDEX IF NOT EXISTS idx_destaques_historico_rodada ON acf_destaques_historico(rodada_id);
CREATE INDEX IF NOT EXISTS idx_destaques_historico_clube ON acf_destaques_historico(clube_id);

-- Snapshot opcional de fontes externas de prováveis. Os IDs externos não são
-- usados como chave do Cartola; o vínculo com atleta_id pode ficar nulo para
-- revisão manual sem bloquear a ingestão do restante da rodada.
CREATE TABLE IF NOT EXISTS acf_provaveis_fontes (
    id BIGSERIAL PRIMARY KEY,
    temporada INTEGER NOT NULL,
    rodada_id INTEGER NOT NULL,
    fonte VARCHAR(50) NOT NULL,
    atleta_externo_id TEXT NOT NULL,
    nome_externo TEXT,
    slug_externo TEXT,
    clube_id INTEGER,
    clube_slug_externo TEXT,
    posicao_id INTEGER,
    atleta_id INTEGER,
    status VARCHAR(30) NOT NULL,
    confianca_mapeamento NUMERIC(5,4) DEFAULT 0,
    metodo_mapeamento VARCHAR(50),
    dados_brutos JSONB NOT NULL DEFAULT '{}'::jsonb,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    capturado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_acf_provaveis_fontes_snapshot
        UNIQUE (temporada, rodada_id, fonte, atleta_externo_id)
);

CREATE INDEX IF NOT EXISTS idx_acf_provaveis_fontes_contexto
    ON acf_provaveis_fontes (temporada, rodada_id, fonte, ativo);
CREATE INDEX IF NOT EXISTS idx_acf_provaveis_fontes_atleta
    ON acf_provaveis_fontes (temporada, rodada_id, fonte, atleta_id);
CREATE INDEX IF NOT EXISTS idx_acf_provaveis_fontes_clube
    ON acf_provaveis_fontes (temporada, rodada_id, clube_id);

-- Vínculos validados manualmente no painel administrativo do Aero Cartola.
-- A ingestão externa não preenche atleta_id nesta tabela; somente a ação
-- explícita do administrador cria uma associação oficial.
CREATE TABLE IF NOT EXISTS acw_provaveis_mapeamentos (
    id BIGSERIAL PRIMARY KEY,
    temporada INTEGER NOT NULL,
    rodada_id INTEGER NOT NULL,
    fonte VARCHAR(50) NOT NULL,
    atleta_externo_id TEXT NOT NULL,
    atleta_id INTEGER,
    atualizado_por INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_acw_provaveis_mapeamento
        UNIQUE (temporada, rodada_id, fonte, atleta_externo_id)
);

CREATE INDEX IF NOT EXISTS idx_acw_provaveis_mapeamento_atleta
    ON acw_provaveis_mapeamentos (temporada, rodada_id, fonte, atleta_id);

-- Inserir credencial padrão do time Aero-RBSV
-- NOTA: As credenciais devem ser inseridas via script Python (insert_default_credential.py)
-- que lê os tokens do arquivo .env. Execute após inicializar o banco:
-- python insert_default_credential.py
