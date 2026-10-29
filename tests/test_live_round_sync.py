import unittest
from unittest.mock import patch

import database

with patch.object(database, 'initialize_database', return_value=True):
    from data_fetcher import DataFetcherService


class LiveRoundSyncTests(unittest.TestCase):
    def _service(self):
        service = DataFetcherService.__new__(DataFetcherService)
        service.scheduler = None
        service.running = False
        service.last_market_status = None
        service.last_fetch_time = None
        service.last_fetch_status = None
        return service

    def test_closed_market_refreshes_only_current_round_scores_and_matches(self):
        service = self._service()
        with patch.object(service, 'get_current_round', return_value=28), \
             patch('data_fetcher.fetch_status_data', return_value={
                 'rodada_atual': 28, 'status_mercado': 2,
             }), \
             patch.object(service, 'fetch_and_store_external_probables', return_value=True), \
             patch.object(service, 'fetch_and_store_partidas_per_round', return_value=True) as matches, \
             patch.object(service, 'fetch_and_store_pontuados', return_value=True) as scores, \
             patch.object(service, 'fetch_and_store_cartola_data') as catalog:
            service.run_fetch_cycle()

        matches.assert_called_once_with(28)
        scores.assert_called_once_with(28, refresh_existing=True)
        catalog.assert_not_called()
        self.assertEqual(service.last_fetch_status, 'success')

    def test_reopened_market_reconciles_previous_round_even_when_present(self):
        service = self._service()
        with patch.object(service, 'get_current_round', return_value=29), \
             patch('data_fetcher.fetch_status_data', return_value={
                 'rodada_atual': 29, 'status_mercado': 1,
             }), \
             patch.object(service, 'fetch_and_store_external_probables', return_value=True), \
             patch.object(service, 'fetch_and_store_cartola_data', return_value=True), \
             patch.object(service, 'fetch_and_store_esquemas', return_value=True), \
             patch.object(service, 'fetch_and_store_partidas_per_round', return_value=True), \
             patch.object(service, 'get_rounds_without_scores', return_value=[]), \
             patch.object(service, 'get_missing_rounds', return_value=[]), \
             patch.object(service, 'fetch_and_store_destaques', return_value=True), \
             patch.object(service, 'fetch_and_store_pontuados', return_value=True) as scores:
            service.run_fetch_cycle()

        scores.assert_called_once_with(28, refresh_existing=True)
        self.assertEqual(service.last_fetch_status, 'success')

    def test_market_closed_uses_live_poll_interval(self):
        service = self._service()
        service.last_market_status = {'status_mercado': 2}
        with patch('data_fetcher.MARKET_CLOSED_INTERVAL_MINUTES', 5):
            self.assertEqual(service._get_next_interval_minutes(), 5)


if __name__ == '__main__':
    unittest.main()
