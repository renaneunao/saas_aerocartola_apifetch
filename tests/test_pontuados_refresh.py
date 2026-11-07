import unittest
from unittest.mock import Mock, call, patch
from requests.exceptions import HTTPError

from api_cartola import API_URL_PONTUADOS, API_URL_PONTUADOS_ATUAL, fetch_pontuados_data
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

    def test_live_round_uses_only_the_live_endpoint(self):
        current = Mock(ok=True, status_code=200)
        current.json.return_value = {'rodada': 34, 'atletas': {'123': {'pontuacao': 4.2}}}
        with patch('api_cartola.requests.get', return_value=current) as get:
            payload = fetch_pontuados_data(34, live=True)

        self.assertEqual(payload['rodada'], 34)
        get.assert_called_once_with(API_URL_PONTUADOS_ATUAL, timeout=(10, 30))

    def test_historical_round_uses_only_the_round_endpoint(self):
        historical = Mock(ok=True, status_code=200)
        historical.json.return_value = {'rodada': 27, 'atletas': {'123': {'pontuacao': 4.2}}}
        with patch('api_cartola.requests.get', return_value=historical) as get:
            payload = fetch_pontuados_data(27)

        self.assertEqual(payload['rodada'], 27)
        get.assert_called_once_with(API_URL_PONTUADOS.format(27), timeout=(10, 30))

    def test_successful_round_endpoint_with_empty_scores_is_not_a_snapshot(self):
        historical = Mock(ok=True, status_code=200)
        historical.json.return_value = {'rodada': 34, 'atletas': {}}
        with patch('api_cartola.requests.get', return_value=historical) as get:
            self.assertIsNone(fetch_pontuados_data(34))
        get.assert_called_once_with(API_URL_PONTUADOS.format(34), timeout=(10, 30))

    def test_live_endpoint_is_rejected_for_a_different_round(self):
        current = Mock(ok=True, status_code=200)
        current.json.return_value = {'rodada': 35, 'atletas': {'123': {'pontuacao': 4.2}}}
        with patch('api_cartola.requests.get', return_value=current) as get:
            self.assertIsNone(fetch_pontuados_data(34, live=True))
        get.assert_called_once_with(API_URL_PONTUADOS_ATUAL, timeout=(10, 30))

    def test_live_endpoint_without_published_athletes_is_not_a_snapshot(self):
        current = Mock(ok=True, status_code=200)
        current.json.return_value = {'rodada': 34, 'atletas': {}}
        with patch('api_cartola.requests.get', return_value=current) as get:
            self.assertIsNone(fetch_pontuados_data(34, live=True))
        get.assert_called_once_with(API_URL_PONTUADOS_ATUAL, timeout=(10, 30))

    def test_historical_error_does_not_call_live_endpoint(self):
        historical = Mock(ok=False, status_code=503)
        historical.raise_for_status.side_effect = HTTPError('upstream unavailable')
        with patch('api_cartola.requests.get', return_value=historical) as get:
            self.assertIsNone(fetch_pontuados_data(34))
        get.assert_called_once_with(API_URL_PONTUADOS.format(34), timeout=(10, 30))


if __name__ == '__main__':
    unittest.main()
