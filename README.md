# Data Fetcher Service - Container 1

Serviço responsável por coletar dados da API do Cartola FC periodicamente e armazenar no PostgreSQL.

## 🚀 Funcionalidades

- **Fetch Periódico**: Busca dados automaticamente a cada 5 minutos
- **Retry Logic**: Tenta novamente em caso de falha (até 3 tentativas)
- **Rate Limiting**: Controla taxa de requisições (10 req/s) para evitar bloqueio da API
- **Verificação de Rodadas**: Preenche automaticamente rodadas faltantes
- **Tracking de Updates**: Controla última atualização de cada tabela

## 📊 Tabelas Gerenciadas

### Tipo 1: Atualização Única (Só se não tiver dados)
- `clubes` - Informações dos clubes
- `posicoes` - Posições dos jogadores (GOL, LAT, ZAG, MEI, ATA, TEC)
- `status` - Status dos jogadores
- `esquemas` - Esquemas táticos disponíveis

### Tipo 2: Atualização por Rodada (Uma vez por rodada)
- `partidas` - Partidas do Campeonato Brasileiro (verifica todas as rodadas de 1 até rodada_atual - 1)
- `destaques` - Jogadores em destaque no mercado
- `pontuados` - Pontuações dos atletas por rodada (verifica todas as rodadas de 1 até rodada_atual - 1)

### Tipo 3: Atualização Contínua (A cada 5 minutos)
- `atletas` - Dados de todos os atletas do mercado

## 🔧 Configuração

### Variáveis de Ambiente

Copie `.env.example` para `.env` e configure:

```bash
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_DB=cartola_manager

# Intervalo de fetch (opcional, padrão: 5 minutos)
FETCH_INTERVAL_MINUTES=5
```

## 🐳 Docker

### Run com Docker Compose

Configure o arquivo `.env` com as credenciais do PostgreSQL e execute:

```bash
docker-compose up -d
```

O docker-compose utiliza a imagem pronta do Docker Hub (`renaneunao/cartola-aero-data-fetcher:latest`), que é buildada automaticamente via GitHub Actions.

### Run Manual

```bash
docker run --env-file .env -d --name cartola-aero-data-fetcher renaneunao/cartola-aero-data-fetcher:latest
```

## 📝 Logs

Os logs são salvos em `data_fetcher.log` e também no stdout (para containers Docker).

## 🔄 Fluxo de Execução

1. Busca status do mercado para obter rodada atual
2. Atualiza dados do mercado (atletas, clubes, posições, status)
3. Verifica e preenche rodadas faltantes de partidas e pontuados
4. Atualiza destaques
5. Agenda próximo ciclo

