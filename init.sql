-- Arquivo de inicialização do banco de dados
-- Todas as tabelas são criadas aqui na ordem correta (respeitando foreign keys)

-- Tabelas base (sem dependências)
CREATE TABLE IF NOT EXISTS clubes (
    id INTEGER PRIMARY KEY,
    nome TEXT,
    abreviacao TEXT,
    slug TEXT,
    apelido TEXT,
    nome_fantasia TEXT,
    url_editoria TEXT
);

CREATE TABLE IF NOT EXISTS posicoes (
    id INTEGER PRIMARY KEY,
    nome TEXT,
    abreviacao TEXT
);

CREATE TABLE IF NOT EXISTS status (
    id INTEGER PRIMARY KEY,
    nome TEXT
);

CREATE TABLE IF NOT EXISTS credenciais (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    env_key TEXT UNIQUE,
    access_token TEXT,
    refresh_token TEXT,
    id_token TEXT,
    estrategia INTEGER DEFAULT 1,
    essential_cookies TEXT
);

CREATE TABLE IF NOT EXISTS esquemas (
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
CREATE TABLE IF NOT EXISTS atletas (
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
    FOREIGN KEY (clube_id) REFERENCES clubes(id),
    FOREIGN KEY (posicao_id) REFERENCES posicoes(id),
    FOREIGN KEY (status_id) REFERENCES status(id)
);

-- Tabelas que dependem de clubes
CREATE TABLE IF NOT EXISTS partidas (
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
    FOREIGN KEY (clube_casa_id) REFERENCES clubes(id),
    FOREIGN KEY (clube_visitante_id) REFERENCES clubes(id)
);

CREATE TABLE IF NOT EXISTS pontuados (
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
    PRIMARY KEY (atleta_id, rodada_id),
    FOREIGN KEY (clube_id) REFERENCES clubes(id),
    FOREIGN KEY (posicao_id) REFERENCES posicoes(id)
);

CREATE TABLE IF NOT EXISTS destaques (
    atleta_id INTEGER PRIMARY KEY,
    posicao TEXT,
    posicao_abreviacao TEXT,
    clube_id INTEGER,
    clube TEXT,
    apelido TEXT,
    preco_editorial REAL,
    escalacoes INTEGER,
    FOREIGN KEY (clube_id) REFERENCES clubes(id)
);

-- Tabelas que dependem de atletas
CREATE TABLE IF NOT EXISTS gato_mestre (
    atleta_id INTEGER PRIMARY KEY,
    minimo_para_valorizar REAL,
    minutos_jogados INTEGER,
    FOREIGN KEY (atleta_id) REFERENCES atletas(atleta_id)
);

-- Tabela de controle de atualizações
CREATE TABLE IF NOT EXISTS updates_tracking (
    table_name TEXT PRIMARY KEY,
    last_update TIMESTAMP DEFAULT NOW()
);
