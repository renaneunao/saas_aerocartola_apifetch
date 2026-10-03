import unittest
from unittest.mock import MagicMock

from models.credenciais import get_credencial_by_env_key, update_tokens_by_env_key


class CredentialRotationTests(unittest.TestCase):
    def test_lookup_uses_the_original_aero_team_row_not_the_most_recent_clone(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value
        cursor.fetchone.return_value = (9, 'Aero-RBSV', 'access-fixture', 'refresh-fixture', 'id-fixture')

        credential = get_credencial_by_env_key(conn, 'AERO_RBSV')

        self.assertEqual(credential['id'], 9)
        query = cursor.execute.call_args.args[0]
        self.assertIn('ORDER BY id ASC', query)
        self.assertNotIn('updated_at DESC', query)

    def test_refresh_updates_only_the_canonical_team_row(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value
        cursor.fetchone.return_value = (9,)

        update_tokens_by_env_key(
            conn,
            'AERO_RBSV',
            access_token='new-access-fixture',
            refresh_token='new-refresh-fixture',
            id_token='new-id-fixture',
        )

        update_sql, values = cursor.execute.call_args.args
        self.assertIn('UPDATE acw_teams', update_sql)
        self.assertIn('WHERE id = %s', update_sql)
        self.assertEqual(tuple(values), ('new-access-fixture', 'new-refresh-fixture', 'new-id-fixture', 9))
        conn.commit.assert_called_once()


if __name__ == '__main__':
    unittest.main()
