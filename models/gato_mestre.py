from utils.utilidades import printdbg

def update_gato_mestre(conn, gato_mestre_data):
    cursor = conn.cursor()

    # Validar se os dados são um dicionário
    if not isinstance(gato_mestre_data, dict):
        printdbg(f"Erro: Formato de dados inválido para gato_mestre. Esperado: dict, Recebido: {type(gato_mestre_data)}")
        return

    # Limpar a tabela antes de inserir novos dados
    cursor.execute('DELETE FROM acf_gato_mestre')
    conn.commit()

    # Inserção em lote para performance
    try:
        from psycopg2.extras import execute_values
        rows = []
        for atleta_id, data in (gato_mestre_data or {}).items():
            try:
                rows.append((
                    int(atleta_id),
                    data.get('minimo_para_valorizar'),
                    data.get('minutos_jogados')
                ))
            except Exception as e:
                printdbg(f"Erro ao montar linha gato_mestre: atleta_id={atleta_id}, data={data}, err={e}")
                continue

        if not rows:
            printdbg("Nenhum dado para inserir em 'gato_mestre'.")
            return

        sql = '''
            INSERT INTO acf_gato_mestre (atleta_id, minimo_para_valorizar, minutos_jogados)
            VALUES %s
            ON CONFLICT (atleta_id) DO UPDATE SET
                minimo_para_valorizar = EXCLUDED.minimo_para_valorizar,
                minutos_jogados = EXCLUDED.minutos_jogados
        '''
        execute_values(cursor, sql, rows, page_size=1000)
        conn.commit()
        printdbg(f"Tabela 'gato_mestre' atualizada com sucesso. Registros: {len(rows)}")
    except Exception as e:
        conn.rollback()
        printdbg(f"Erro em inserção em lote de 'gato_mestre': {e}")