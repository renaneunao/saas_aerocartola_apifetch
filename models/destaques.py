from utils.utilidades import printdbg

def create_destaques_table(conn):
    cursor = conn.cursor()
    cursor.execute('''
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
        )
    ''')
    conn.commit()

def update_destaques(conn, destaques_data):
    cursor = conn.cursor()

    # Validar se os dados são uma lista
    if not isinstance(destaques_data, list):
        printdbg(f"Erro: Formato de dados inválido para destaques. Esperado: lista, Recebido: {type(destaques_data)}")
        return

    # Limpar a tabela antes de inserir novos dados
    cursor.execute('DELETE FROM destaques')
    conn.commit()

    for destaque in destaques_data:
        # Verificar se o item é um dicionário com a chave 'Atleta'
        if not isinstance(destaque, dict) or 'Atleta' not in destaque:
            printdbg(f"Formato de dados inesperado em destaques: {destaque}")
            continue

        try:
            atleta = destaque['Atleta']
            cursor.execute('''
                INSERT INTO destaques (
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
                destaque.get('escalacoes')
            ))
        except Exception as e:
            printdbg(f"Erro ao processar item de destaques: {destaque}")
            printdbg(f"Detalhes do erro: {e}")
            continue

    conn.commit()
    printdbg("Tabela 'destaques' atualizada com sucesso.")