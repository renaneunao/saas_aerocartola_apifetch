"""
Container 1 - Data Fetcher Service
Serviço responsável por coletar dados da API do Cartola FC periodicamente
e armazenar no PostgreSQL.

Funcionalidades:
- Fetch periódico a cada 5 minutos
- Retry logic para falhas de API
- Rate limiting
- Integração com APIs do Cartola FC (atletas, clubes, partidas, destaques, etc.)
"""

import os
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from functools import wraps
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from database import get_db_connection, close_db_connection
from utils.utilidades import printdbg
from api_cartola import (
    fetch_cartola_data,
    fetch_status_data,
    fetch_partidas_data,
    fetch_pontuados_data,
    fetch_esquemas_data,
    fetch_destaques_data
)
# Removidos: CBF, Joga10 e Prováveis - não são responsabilidade deste container

# Importar modelos para criar tabelas e atualizar dados
from models.atletas import create_atletas_table, update_atletas
from models.clubes import create_clubes_table, update_clubes
from models.status import create_status_table, update_status
from models.posicoes import create_posicoes_table, update_posicoes
from models.partidas import create_partidas_table, update_partidas
from models.pontuados import create_pontuados_table, update_pontuados
from models.esquemas import create_esquemas_table, update_esquemas
from models.destaques import create_destaques_table, update_destaques
# Removidos: provaveis_cartola - não é responsabilidade deste container

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data_fetcher.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Rate limiting simples
class RateLimiter:
    """Limita a taxa de requisições para evitar rate limit da API"""
    def __init__(self, max_calls: int = 10, period: float = 1.0):
        self.max_calls = max_calls
        self.period = period
        self.calls = []
    
    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            # Remove chamadas antigas do período
            self.calls = [call_time for call_time in self.calls if now - call_time < self.period]
            
            # Se excedeu o limite, espera
            if len(self.calls) >= self.max_calls:
                sleep_time = self.period - (now - self.calls[0])
                if sleep_time > 0:
                    logger.info(f"Rate limit atingido. Aguardando {sleep_time:.2f}s...")
                    time.sleep(sleep_time)
                    # Limpa a lista novamente após esperar
                    now = time.time()
                    self.calls = [call_time for call_time in self.calls if now - call_time < self.period]
            
            self.calls.append(time.time())
            return func(*args, **kwargs)
        return wrapper

# Instância global do rate limiter (10 requisições por segundo)
rate_limiter = RateLimiter(max_calls=10, period=1.0)

def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Decorator para retry automático em caso de falha"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Tentativa {attempt + 1}/{max_retries} falhou para {func.__name__}: {e}. "
                            f"Tentando novamente em {current_delay:.2f}s..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"Todas as tentativas falharam para {func.__name__}: {e}")
            
            raise last_exception
        return wrapper
    return decorator

class DataFetcherService:
    """Serviço principal para fetch de dados do Cartola FC"""
    
    def __init__(self):
        self.scheduler = None
        self.running = False
        self.last_fetch_time = None
        self.last_fetch_status = None
    
    # ========== FUNÇÕES AUXILIARES DE CONTROLE DE ATUALIZAÇÃO ==========
    
    def table_has_data(self, table_name: str) -> bool:
        """Verifica se uma tabela tem dados"""
        conn = get_db_connection()
        if not conn:
            return False
        try:
            cursor = conn.cursor()
            cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
            count = cursor.fetchone()[0]
            cursor.close()
            return count > 0
        except Exception as e:
            logger.error(f"Erro ao verificar dados da tabela {table_name}: {e}")
            return False
        finally:
            close_db_connection(conn)
    
    def get_missing_rounds(self, table_name: str, rodada_atual: int, max_rounds_to_check: int = None) -> list[int]:
        """
        Retorna lista de rodadas faltantes para uma tabela.
        
        Para partidas: verifica todas as rodadas de 1 até rodada_atual
        Para pontuados: verifica todas as rodadas de 1 até rodada_atual - 1
        """
        conn = get_db_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor()
            
            # Determinar range de rodadas a verificar
            if table_name == 'pontuados':
                # Pontuados: até rodada anterior
                min_round = 1
                max_round = rodada_atual - 1 if rodada_atual > 1 else 0
            elif table_name == 'partidas':
                # Partidas: até rodada anterior (rodada_atual - 1)
                min_round = 1
                max_round = rodada_atual - 1 if rodada_atual > 1 else 0
            else:
                cursor.close()
                return []
            
            if max_round < min_round:
                cursor.close()
                return []
            
            # Se especificado, limitar quantidade de rodadas a verificar
            if max_rounds_to_check:
                min_round = max(min_round, max_round - max_rounds_to_check + 1)
            
            # Buscar todas as rodadas que existem no banco
            cursor.execute(f"SELECT DISTINCT rodada_id FROM {table_name} WHERE rodada_id BETWEEN %s AND %s", (min_round, max_round))
            existing_rounds = {row[0] for row in cursor.fetchall()}
            
            # Encontrar rodadas faltantes
            all_rounds = set(range(min_round, max_round + 1))
            missing_rounds = sorted(list(all_rounds - existing_rounds), reverse=True)  # Ordena do maior para o menor
            
            cursor.close()
            return missing_rounds
            
        except Exception as e:
            logger.error(f"Erro ao verificar rodadas faltantes para {table_name}: {e}")
            return []
        finally:
            close_db_connection(conn)
    
    def was_updated_in_round(self, table_name: str, rodada: int) -> bool:
        """
        Verifica se uma tabela já foi atualizada na rodada atual.
        Para partidas, verifica se já existe partida para essa rodada.
        Para outras tabelas por rodada, verifica last_update (assume 1x por rodada dentro de 24h).
        """
        conn = get_db_connection()
        if not conn:
            return False
        try:
            cursor = conn.cursor()
            
            # Para partidas, verificar se já existe partida para essa rodada
            if table_name == 'partidas':
                cursor.execute("SELECT COUNT(*) FROM partidas WHERE rodada_id = %s", (rodada,))
                count = cursor.fetchone()[0]
                cursor.close()
                return count > 0
            
            # Para pontuados, verificar se já existe pontuados para essa rodada
            if table_name == 'pontuados':
                cursor.execute("SELECT COUNT(*) FROM pontuados WHERE rodada_id = %s", (rodada,))
                count = cursor.fetchone()[0]
                cursor.close()
                return count > 0
            
            # Para destaques, verificar last_update na tracking (assume 1x por rodada)
            if table_name == 'destaques':
                cursor.execute("""
                    SELECT last_update 
                    FROM updates_tracking 
                    WHERE table_name = %s
                """, (table_name,))
                result = cursor.fetchone()
                cursor.close()
                # Se foi atualizado nas últimas 24h, assume que já foi nesta rodada
                if result and result[0]:
                    from datetime import timedelta
                    if result[0] > datetime.now() - timedelta(hours=24):
                        return True
            
            cursor.close()
            return False
        except Exception as e:
            logger.error(f"Erro ao verificar updates_tracking para {table_name}: {e}")
            return False
        finally:
            close_db_connection(conn)
    
    def mark_table_updated(self, table_name: str):
        """Marca uma tabela como atualizada no updates_tracking"""
        conn = get_db_connection()
        if not conn:
            return
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO updates_tracking (table_name, last_update)
                VALUES (%s, NOW())
                ON CONFLICT (table_name) 
                DO UPDATE SET last_update = NOW()
            """, (table_name,))
            conn.commit()
            cursor.close()
        except Exception as e:
            logger.error(f"Erro ao marcar {table_name} como atualizada: {e}")
            conn.rollback()
        finally:
            close_db_connection(conn)
    
    def get_current_round(self) -> Optional[int]:
        """Obtém a rodada atual do status da API"""
        try:
            status_data = fetch_status_data()
            if status_data and 'rodada_atual' in status_data:
                return status_data['rodada_atual']
            elif status_data and 'mercado' in status_data:
                # Algumas versões da API retornam dentro de 'mercado'
                mercado = status_data['mercado']
                if isinstance(mercado, dict) and 'rodada_atual' in mercado:
                    return mercado['rodada_atual']
            logger.warning("Não foi possível determinar a rodada atual")
            return None
        except Exception as e:
            logger.error(f"Erro ao obter rodada atual: {e}")
            return None
    
    @retry_on_failure(max_retries=3, delay=2.0)
    @rate_limiter
    def fetch_and_store_cartola_data(self) -> bool:
        """
        Busca e armazena dados principais do Cartola (mercado/atletas)
        
        Lógica de atualização:
        - clubes, posicoes, status: Só atualiza se não tiverem dados
        - atletas: Sempre atualiza (a cada 5 minutos)
        """
        try:
            logger.info("Iniciando fetch de dados do mercado Cartola...")
            data = fetch_cartola_data()
            
            if not data:
                logger.error("Falha ao obter dados do mercado")
                return False
            
            conn = get_db_connection()
            if not conn:
                logger.error("Falha ao conectar ao banco de dados")
                return False
            
            try:
                # Criar tabelas se não existirem
                create_clubes_table(conn)
                create_posicoes_table(conn)
                create_status_table(conn)
                create_atletas_table(conn)
                
                # Obter rodada atual
                rodada_atual = self.get_current_round()
                if not rodada_atual:
                    logger.warning("Rodada atual não disponível, usando rodada padrão")
                    rodada_atual = data.get('rodada_atual', 1)
                
                # ===== TABELAS QUE SÓ ATUALIZAM SE NÃO TIVEREM DADOS =====
                
                # Atualizar clubes (só se não tiver dados)
                if 'clubes' in data:
                    if not self.table_has_data('clubes'):
                        logger.info("Atualizando clubes (primeira vez)...")
                        update_clubes(conn, data['clubes'])
                        logger.info(f"Clubes atualizados: {len(data['clubes'])}")
                    else:
                        logger.info("Clubes já possui dados, pulando atualização")
                    # Sempre marca no tracking, mesmo se pulou
                    self.mark_table_updated('clubes')
                
                # Atualizar posições (só se não tiver dados)
                if 'posicoes' in data:
                    if not self.table_has_data('posicoes'):
                        logger.info("Atualizando posições (primeira vez)...")
                        update_posicoes(conn, data['posicoes'])
                        logger.info(f"Posições atualizadas: {len(data['posicoes'])}")
                    else:
                        logger.info("Posições já possui dados, pulando atualização")
                    # Sempre marca no tracking, mesmo se pulou
                    self.mark_table_updated('posicoes')
                
                # Atualizar status (só se não tiver dados)
                if 'status' in data:
                    if not self.table_has_data('status'):
                        logger.info("Atualizando status (primeira vez)...")
                        update_status(conn, data['status'])
                        logger.info(f"Status atualizados: {len(data['status'])}")
                    else:
                        logger.info("Status já possui dados, pulando atualização")
                    # Sempre marca no tracking, mesmo se pulou
                    self.mark_table_updated('status')
                
                # ===== TABELAS QUE ATUALIZAM SEMPRE (A CADA 5 MIN) =====
                
                # Atualizar atletas sempre
                if 'atletas' in data and data['atletas']:
                    logger.info("Processando atletas...")
                    atletas_data = []
                    for atleta in data['atletas']:
                        atleta_data = {
                            'atleta_id': atleta.get('atleta_id'),
                            'clube_id': atleta.get('clube_id'),
                            'posicao_id': atleta.get('posicao_id'),
                            'status_id': atleta.get('status_id'),
                            'pontos_num': atleta.get('pontos_num'),
                            'media_num': atleta.get('media_num'),
                            'variacao_num': atleta.get('variacao_num'),
                            'preco_num': atleta.get('preco_num'),
                            'jogos_num': atleta.get('jogos_num'),
                            'entrou_em_campo': atleta.get('entrou_em_campo', False),
                            'slug': atleta.get('slug'),
                            'apelido': atleta.get('apelido'),
                            'nome': atleta.get('nome'),
                            'foto': atleta.get('foto')
                        }
                        atletas_data.append(atleta_data)
                    
                    update_atletas(conn, atletas_data, rodada_atual)
                    logger.info(f"Atletas atualizados: {len(atletas_data)}")
                    self.mark_table_updated('atletas')
                
                logger.info("Dados do mercado Cartola processados com sucesso")
                return True
                
            finally:
                close_db_connection(conn)
                
        except Exception as e:
            logger.error(f"Erro ao buscar/armazenar dados do Cartola: {e}", exc_info=True)
            return False
    
    @retry_on_failure(max_retries=3, delay=2.0)
    @rate_limiter
    def fetch_and_store_status(self) -> bool:
        """Busca e armazena status do mercado"""
        try:
            logger.info("Buscando status do mercado...")
            status_data = fetch_status_data()
            
            if not status_data:
                logger.error("Falha ao obter status do mercado")
                return False
            
            # Status geralmente não precisa ser armazenado separadamente
            # já que é atualizado junto com os dados do mercado
            # Mas podemos usar para verificar estado do mercado
            self.last_fetch_status = status_data
            logger.info("Status do mercado obtido com sucesso")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao buscar status: {e}", exc_info=True)
            return False
    
    @retry_on_failure(max_retries=3, delay=2.0)
    @rate_limiter
    def fetch_and_store_partidas_per_round(self, rodada: int) -> bool:
        """
        Busca e armazena partidas de uma rodada específica
        Lógica: Atualiza apenas uma vez por rodada
        """
        try:
            # Verificar se já foi atualizado nesta rodada
            if self.was_updated_in_round('partidas', rodada):
                logger.info(f"Partidas da rodada {rodada} já foram atualizadas, pulando...")
                return True
            
            logger.info(f"Buscando partidas da rodada {rodada}...")
            partidas_data = fetch_partidas_data(rodada)
            
            if not partidas_data:
                logger.warning(f"Nenhuma partida encontrada para rodada {rodada}")
                return False
            
            conn = get_db_connection()
            if not conn:
                logger.error("Falha ao conectar ao banco de dados")
                return False
            
            try:
                create_partidas_table(conn)
                update_partidas(conn, partidas_data, rodada)
                self.mark_table_updated('partidas')
                logger.info(f"Partidas da rodada {rodada} armazenadas com sucesso")
                return True
            finally:
                close_db_connection(conn)
                
        except Exception as e:
            logger.error(f"Erro ao buscar/armazenar partidas da rodada {rodada}: {e}", exc_info=True)
            return False
    
    @retry_on_failure(max_retries=3, delay=2.0)
    @rate_limiter
    def fetch_and_store_pontuados(self, rodada: int) -> bool:
        """
        Busca e armazena atletas pontuados de uma rodada
        Lógica: Atualiza uma vez por rodada (o modelo já verifica duplicação)
        """
        try:
            logger.info(f"Buscando atletas pontuados da rodada {rodada}...")
            pontuados_data = fetch_pontuados_data(rodada)
            
            if not pontuados_data:
                logger.warning(f"Nenhum atleta pontuado encontrado para rodada {rodada}")
                return False
            
            conn = get_db_connection()
            if not conn:
                logger.error("Falha ao conectar ao banco de dados")
                return False
            
            try:
                create_pontuados_table(conn)
                update_pontuados(conn, pontuados_data, rodada)
                self.mark_table_updated('pontuados')
                logger.info(f"Atletas pontuados da rodada {rodada} armazenados com sucesso")
                return True
            finally:
                close_db_connection(conn)
                
        except Exception as e:
            logger.error(f"Erro ao buscar/armazenar pontuados da rodada {rodada}: {e}", exc_info=True)
            return False
    
    @retry_on_failure(max_retries=2, delay=3.0)
    @rate_limiter
    def fetch_and_store_esquemas(self) -> bool:
        """
        Busca e armazena esquemas táticos
        Lógica: Só atualiza se não tiver dados
        """
        try:
            # Verificar se já tem dados
            if self.table_has_data('esquemas'):
                logger.info("Esquemas já possui dados, pulando atualização")
                # Sempre marca no tracking, mesmo se pulou
                self.mark_table_updated('esquemas')
                return True
            
            logger.info("Buscando esquemas táticos...")
            esquemas_data = fetch_esquemas_data()
            
            if not esquemas_data:
                logger.warning("Nenhum esquema encontrado")
                return False
            
            conn = get_db_connection()
            if not conn:
                logger.error("Falha ao conectar ao banco de dados")
                return False
            
            try:
                # Verificar se já tem dados antes de atualizar
                if not self.table_has_data('esquemas'):
                    create_esquemas_table(conn)
                    update_esquemas(conn, esquemas_data)
                    logger.info(f"Esquemas atualizados: {len(esquemas_data)}")
                else:
                    logger.info("Esquemas já possui dados, pulando atualização")
                # Sempre marca no tracking, mesmo se pulou
                self.mark_table_updated('esquemas')
                return True
            finally:
                close_db_connection(conn)
                
        except Exception as e:
            logger.error(f"Erro ao buscar/armazenar esquemas: {e}", exc_info=True)
            return False
    
    @retry_on_failure(max_retries=2, delay=3.0)
    @rate_limiter
    def fetch_and_store_destaques(self, rodada: int) -> bool:
        """
        Busca e armazena destaques do mercado
        Lógica: Atualiza uma vez por rodada
        """
        try:
            # Verificar se já foi atualizado nesta rodada
            if self.was_updated_in_round('destaques', rodada):
                logger.info(f"Destaques da rodada {rodada} já foram atualizados, pulando...")
                return True
            
            logger.info("Buscando destaques do mercado...")
            destaques_data = fetch_destaques_data()
            
            if not destaques_data:
                logger.warning("Nenhum destaque encontrado")
                return False
            
            conn = get_db_connection()
            if not conn:
                logger.error("Falha ao conectar ao banco de dados")
                return False
            
            try:
                create_destaques_table(conn)
                update_destaques(conn, destaques_data)
                self.mark_table_updated('destaques')
                logger.info(f"Destaques atualizados: {len(destaques_data)} itens")
                return True
            finally:
                close_db_connection(conn)
                
        except Exception as e:
            logger.error(f"Erro ao buscar/armazenar destaques: {e}", exc_info=True)
            return False
    
    def run_fetch_cycle(self):
        """Executa um ciclo completo de fetch de dados"""
        start_time = time.time()
        logger.info("=" * 60)
        logger.info(f"Iniciando ciclo de fetch - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        
        results = {
            'cartola_data': False,
            'status': False,
            'partidas': False,
            'pontuados': False
        }
        
        try:
            # 0. Validar rodada atual PRIMEIRO (antes de qualquer processamento)
            rodada_atual = self.get_current_round()
            if not rodada_atual or rodada_atual < 1:
                logger.error("Não foi possível obter rodada atual válida. Abortando ciclo.")
                self.last_fetch_status = 'error'
                return
            
            logger.info(f"Rodada atual validada: {rodada_atual}")
            
            # 1. Buscar status do mercado
            results['status'] = self.fetch_and_store_status()
            
            # 2. Buscar dados principais do Cartola (atletas, clubes, etc.)
            results['cartola_data'] = self.fetch_and_store_cartola_data()
            
            # 3. Buscar esquemas (só se não tiver dados)
            self.fetch_and_store_esquemas()
            
            # 4. Buscar partidas, destaques e pontuados
            if rodada_atual:
                logger.info(f"Rodada atual detectada: {rodada_atual}")
                
                # PARTIDAS: Verificar TODAS as rodadas faltantes (de 1 até rodada_atual - 1)
                if rodada_atual > 1:
                    logger.info("Verificando rodadas de partidas faltantes...")
                    missing_partidas = self.get_missing_rounds('partidas', rodada_atual)
                    if missing_partidas:
                        logger.info(f"Rodadas de partidas faltantes encontradas: {missing_partidas}")
                        for rodada_missing in missing_partidas:
                            logger.info(f"Buscando partidas da rodada {rodada_missing}...")
                            self.fetch_and_store_partidas_per_round(rodada_missing)
                        results['partidas'] = True
                    else:
                        logger.info(f"Todas as partidas das rodadas (1 até {rodada_atual - 1}) já estão atualizadas")
                        # Marca no tracking mesmo se não precisou buscar nada
                        self.mark_table_updated('partidas')
                        results['partidas'] = True
                else:
                    logger.info("Rodada atual é 1, não há rodadas anteriores para buscar partidas")
                    results['partidas'] = True
                
                # Destaques da rodada atual (uma vez por rodada)
                self.fetch_and_store_destaques(rodada_atual)
                
                # PONTUADOS: Verificar TODAS as rodadas faltantes (de 1 até rodada_atual - 1)
                if rodada_atual > 1:
                    logger.info("Verificando rodadas de pontuados faltantes...")
                    missing_pontuados = self.get_missing_rounds('pontuados', rodada_atual)
                    if missing_pontuados:
                        logger.info(f"Rodadas de pontuados faltantes encontradas: {missing_pontuados}")
                        for rodada_missing in missing_pontuados:
                            logger.info(f"Buscando pontuados da rodada {rodada_missing}...")
                            self.fetch_and_store_pontuados(rodada_missing)
                        results['pontuados'] = True
                    else:
                        logger.info(f"Todos os pontuados das rodadas (1 até {rodada_atual - 1}) já estão atualizados")
                        results['pontuados'] = True
                else:
                    logger.info("Rodada atual é 1, não há rodada anterior para buscar pontuados")
                    results['pontuados'] = True  # Considera sucesso pois não há o que buscar
            
            elapsed_time = time.time() - start_time
            
            # Resumo do ciclo
            logger.info("=" * 60)
            logger.info("Resumo do ciclo de fetch:")
            for task, success in results.items():
                status = "[OK]" if success else "[ERRO]"
                logger.info(f"  {status} {task}: {'Sucesso' if success else 'Falhou'}")
            logger.info(f"Tempo total: {elapsed_time:.2f}s")
            logger.info("=" * 60)
            
            self.last_fetch_time = datetime.now()
            self.last_fetch_status = 'success' if all(results.values()) else 'partial'
            
        except Exception as e:
            logger.error(f"Erro crítico no ciclo de fetch: {e}", exc_info=True)
            self.last_fetch_status = 'error'
    
    def start(self, interval_minutes: int = 5):
        """Inicia o serviço com agendamento periódico"""
        if self.running:
            logger.warning("Serviço já está em execução")
            return
        
        logger.info(f"Iniciando Data Fetcher Service (intervalo: {interval_minutes} minutos)")
        
        # Executar primeiro ciclo imediatamente
        self.run_fetch_cycle()
        
        # Configurar agendamento
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(
            self.run_fetch_cycle,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id='fetch_cycle',
            name='Ciclo de Fetch de Dados',
            replace_existing=True
        )
        
        self.scheduler.start()
        self.running = True
        logger.info("[OK] Data Fetcher Service iniciado com sucesso")
    
    def stop(self):
        """Para o serviço"""
        if not self.running:
            logger.warning("Serviço já está parado")
            return
        
        logger.info("Parando Data Fetcher Service...")
        
        if self.scheduler:
            self.scheduler.shutdown(wait=True)
        
        self.running = False
        logger.info("[OK] Data Fetcher Service parado")
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna status do serviço"""
        return {
            'running': self.running,
            'last_fetch_time': self.last_fetch_time.isoformat() if self.last_fetch_time else None,
            'last_fetch_status': self.last_fetch_status
        }


# Instância global do serviço
fetcher_service = DataFetcherService()


def main():
    """Função principal para executar o serviço"""
    import signal
    import sys
    
    def signal_handler(sig, frame):
        logger.info("Recebido sinal de interrupção. Parando serviço...")
        fetcher_service.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Iniciar serviço (5 minutos de intervalo)
        # Obter intervalo de variável de ambiente ou usar padrão
        interval_minutes = int(os.getenv('FETCH_INTERVAL_MINUTES', 5))
        fetcher_service.start(interval_minutes=interval_minutes)
        
        # Manter o processo vivo
        logger.info("Serviço em execução. Pressione Ctrl+C para parar.")
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Interrompido pelo usuário")
    except Exception as e:
        logger.error(f"Erro fatal: {e}", exc_info=True)
    finally:
        fetcher_service.stop()


if __name__ == "__main__":
    main()

