from utils.utilidades import printdbg

def update_destaques(conn, destaques_data):
    cursor = conn.cursor()

    # Validar se os dados são uma lista
    if not isinstance(destaques_data, list):
        printdbg(f"Erro: Formato de dados inválido para destaques. Esperado: lista, Recebido: {type(destaques_data)}")
        printdbg(f"Conteúdo recebido: {destaques_data}")
        return

    # Limpar a tabela antes de inserir novos dados
    cursor.execute('DELETE FROM acf_destaques')
    conn.commit()

    total_processados = 0
    total_erros = 0

    for destaque in destaques_data:
        # Verificar se o item é um dicionário com a chave 'Atleta'
        if not isinstance(destaque, dict) or 'Atleta' not in destaque:
            printdbg(f"Formato de dados inesperado em destaques: {destaque}")
            total_erros += 1
            continue

        try:
            atleta = destaque['Atleta']
            
            # Debug: verificar estrutura dos dados
            escalacoes = destaque.get('escalacoes')
            if escalacoes is None:
                # Tentar outras possíveis chaves
                escalacoes = destaque.get('escalações') or destaque.get('Escalacoes') or destaque.get('Escalações')
                if escalacoes is None and isinstance(atleta, dict):
                    escalacoes = atleta.get('escalacoes') or atleta.get('escalações') or atleta.get('Escalacoes')
            
            # Log de debug para o primeiro item
            if total_processados == 0:
                printdbg(f"Estrutura do primeiro destaque (debug): {list(destaque.keys())}")
                printdbg(f"Estrutura do Atleta (debug): {list(atleta.keys()) if isinstance(atleta, dict) else 'Não é dict'}")
                printdbg(f"Valor de escalacoes encontrado: {escalacoes}")
            
            cursor.execute('''
                INSERT INTO acf_destaques (
                    atleta_id, posicao, posicao_abreviacao, clube_id, clube, 
                    apelido, preco_editorial, escalacoes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (atleta_id) DO UPDATE SET
                    posicao = EXCLUDED.posicao,
                    posicao_abreviacao = EXCLUDED.posicao_abreviacao,
                    clube_id = EXCLUDED.clube_id,
                    clube = EXCLUDED.clube,
                    apelido = EXCLUDED.apelido,
                    preco_editorial = EXCLUDED.preco_editorial,
                    escalacoes = EXCLUDED.escalacoes
            ''', (
                atleta.get('atleta_id'),
                destaque.get('posicao'),
                destaque.get('posicao_abreviacao'),
                destaque.get('clube_id'),
                destaque.get('clube'),
                atleta.get('apelido'),
                atleta.get('preco_editorial'),
                escalacoes
            ))
            total_processados += 1
        except Exception as e:
            printdbg(f"Erro ao processar item de destaques: {destaque}")
            printdbg(f"Detalhes do erro: {e}")
            import traceback
            printdbg(f"Traceback: {traceback.format_exc()}")
            total_erros += 1
            continue

    conn.commit()
    printdbg(f"Tabela 'destaques' atualizada com sucesso. Processados: {total_processados}, Erros: {total_erros}")