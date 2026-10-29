import unittest
from unittest.mock import patch

from models.pontuados import update_pontuados


class _Cursor:
    def __init__(self, existing):
        self.existing = existing

    def execute(self, *_args):
        pass

    def fetchone(self):
        return (self.existing,)


class _Connection:
    def __init__(self, existing=1):
        self.cursor_instance = _Cursor(existing)
        self.commits = 0

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commits += 1


class PontuadosRefreshTests(unittest.TestCase):
    def setUp(self):
        self.payload = {'atletas': {
            '123': {'pontuacao': 4.2, 'entrou_em_campo': True, 'apelido': 'Teste', 'scout': {'G': 1}}
        }}

    def test_historical_existing_round_is_still_skipped_by_default(self):
        conn = _Connection(existing=1)
        with patch('utils.utilidades.get_temporada_atual', return_value=2026), \
             patch('psycopg2.extras.execute_values') as execute_values:
            update_pontuados(conn, self.payload, 27)

        execute_values.assert_not_called()

    def test_live_refresh_upserts_rows_even_if_the_round_already_exists(self):
        conn = _Connection(existing=1)
        with patch('utils.utilidades.get_temporada_atual', return_value=2026), \
             patch('psycopg2.extras.execute_values') as execute_values:
            update_pontuados(conn, self.payload, 28, refresh_existing=True)

        execute_values.assert_called_once()
        self.assertEqual(conn.commits, 2)
        self.assertIn('ON CONFLICT (atleta_id, rodada_id)', execute_values.call_args.args[1])


if __name__ == '__main__':
    unittest.main()
