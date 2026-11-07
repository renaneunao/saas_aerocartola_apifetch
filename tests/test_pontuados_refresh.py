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

    def test_current_endpoint_is_used_only_when_historical_endpoint_returns_400(self):
        historical = Mock(ok=False, status_code=400)
        current = Mock(ok=True, status_code=200)
        current.json.return_value = {'rodada': 34, 'atletas': {'123': {'pontuacao': 4.2}}}
        with patch('api_cartola.requests.get', side_effect=[historical, current]) as get:
            payload = fetch_pontuados_data(34)

        self.assertEqual(payload['rodada'], 34)
        self.assertEqual(get.call_args_list, [
            call(API_URL_PONTUADOS.format(34), timeout=(10, 30)),
            call(API_URL_PONTUADOS_ATUAL, timeout=(10, 30)),
        ])

    def test_current_endpoint_fallback_is_rejected_for_a_different_round(self):
        historical = Mock(ok=False, status_code=400)
        current = Mock(ok=True, status_code=200)
        current.json.return_value = {'rodada': 35, 'atletas': {}}
        with patch('api_cartola.requests.get', side_effect=[historical, current]):
            self.assertIsNone(fetch_pontuados_data(34))

    def test_current_endpoint_fallback_is_rejected_until_at_least_one_athlete_is_published(self):
        historical = Mock(ok=False, status_code=400)
        current = Mock(ok=True, status_code=200)
        current.json.return_value = {'rodada': 34, 'atletas': {}}
        with patch('api_cartola.requests.get', side_effect=[historical, current]):
            self.assertIsNone(fetch_pontuados_data(34))

    def test_non_400_historical_error_does_not_fallback_to_current_round(self):
        historical = Mock(ok=False, status_code=503)
        historical.raise_for_status.side_effect = HTTPError('upstream unavailable')
        with patch('api_cartola.requests.get', return_value=historical) as get:
            self.assertIsNone(fetch_pontuados_data(34))
        get.assert_called_once_with(API_URL_PONTUADOS.format(34), timeout=(10, 30))


if __name__ == '__main__':
    unittest.main()
