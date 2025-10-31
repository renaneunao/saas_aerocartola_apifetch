"""
Script de teste para verificar se o ciclo completo do data_fetcher funciona
"""
from data_fetcher import DataFetcherService
import logging

# Configurar logging para ver tudo
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    print("=" * 60)
    print("TESTE DO CICLO COMPLETO DO DATA FETCHER")
    print("=" * 60)
    
    try:
        service = DataFetcherService()
        print("\nExecutando um ciclo completo...")
        print("-" * 60)
        
        service.run_fetch_cycle()
        
        print("-" * 60)
        status = service.get_status()
        print("\nStatus final do serviço:")
        print(f"  Running: {status.get('running', False)}")
        print(f"  Last Fetch Time: {status.get('last_fetch_time', 'N/A')}")
        print(f"  Last Fetch Status: {status.get('last_fetch_status', 'N/A')}")
        
        print("\n[OK] TESTE CONCLUIDO COM SUCESSO!")
        
    except Exception as e:
        print(f"\n[ERRO] ERRO NO TESTE: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())

