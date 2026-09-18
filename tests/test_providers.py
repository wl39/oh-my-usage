"""Offline contract tests: synthetic credentials, HTTP responses and native stores."""
import base64
import contextlib
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from oh_my_usage import cache, config, customize, settings
from oh_my_usage.__main__ import main
from oh_my_usage.paths import cache_directory
from oh_my_usage.providers import adapters, collector, mappers, native
from oh_my_usage.providers.common import Credential, Detection, ProviderError, iso, progress
from oh_my_usage.providers.http import Client

NOW = 1789747200
RESET = '2026-09-19T00:00:00+00:00'
FIXTURES = {
    'antigravity': {'response': {'groups': [{'buckets': [
        {'bucketId': 'gemini-5h', 'remainingFraction': .75, 'resetTime': RESET},
        {'bucketId': 'gemini-weekly', 'remainingFraction': .5},
        {'bucketId': '3p-5h', 'remainingFraction': 1}, {'bucketId': '3p-weekly', 'remainingFraction': .9}]}]}},
    'claude': {'five_hour': {'utilization': 25, 'resets_at': RESET}, 'seven_day': {'utilization': 50},
               'extra_usage': {'is_enabled': True, 'used_credits': 125, 'monthly_limit': 2000}},
    'codex': {'rateLimitsByLimitId': {'codex': {'primary': {'usedPercent': 25, 'windowDurationMins': 10080,
                                                          'resetsAt': 1789776000}}}},
    'copilot': {'quota_snapshots': {'premium_interactions': {'entitlement': 300, 'remaining': 225}},
                'quota_reset_date': '2026-10-01'},
    'cursor': {'planUsage': {'totalSpend': 500, 'limit': 2000, 'autoPercentUsed': 10, 'apiPercentUsed': 15},
               'billingCycleEnd': 1789776000000},
    'devin': {'userStatus': {'planStatus': {'dailyQuotaRemainingPercent': 75, 'weeklyQuotaRemainingPercent': 50,
                                          'overageBalanceMicros': 1500000}}},
    'grok': {'config': {'creditUsagePercent': 25, 'currentPeriod': {'type': 'USAGE_PERIOD_TYPE_WEEKLY',
                        'start': '2026-09-12T00:00:00Z', 'end': RESET}, 'onDemandCap': {'val': 2500}}},
    'ollama': {'limits': {'session': {'usage': .25}, 'weekly': {'usage': .5}}, 'activity': {'cost': '1.25'}},
    'opencode': {'usage': {'rolling': {'percent': 25, 'resetsAt': RESET}, 'weekly': {'percent': 50}, 'monthly': {'percent': 75}}},
    'openrouter': ({'data': {'total_credits': 20, 'total_usage': 5}},
                   {'data': {'limit': 10, 'limit_remaining': 7, 'usage': 99, 'usage_daily': 0, 'usage_weekly': 2, 'usage_monthly': 3}}),
    'zai': {'data': {'limits': [{'type': 'CREDIT_LIMIT', 'unit': 3, 'number': 5, 'percentage': 25, 'nextResetTime': 1789776000000},
                               {'type': 'TOKENS_LIMIT', 'unit': 6, 'number': 1, 'percentage': 50},
                               {'type': 'TIME_LIMIT', 'usage': 100, 'currentValue': 12}]}}
}


class MapperTests(unittest.TestCase):
    def test_all_eleven_providers_have_live_meter_contracts(self):
        self.assertEqual(set(FIXTURES), set(adapters.PROVIDERS))
        for provider, data in FIXTURES.items():
            with self.subTest(provider=provider):
                fn = getattr(mappers, provider)
                rows = fn(*data) if provider == 'openrouter' else fn(data)
                self.assertTrue(rows)
                first = rows[0]
                self.assertAlmostEqual(first['used'] / first['limit'], .25)
                self.assertTrue(all('id' in row for row in rows))

    def test_missing_fields_are_absent_never_zero(self):
        for provider in FIXTURES:
            with self.subTest(provider=provider):
                if provider == 'grok':
                    with self.assertRaises(ProviderError): mappers.grok({})
                else:
                    data = mappers.openrouter({}, {}) if provider == 'openrouter' else getattr(mappers, provider)({})
                    self.assertEqual(data, [])
        self.assertEqual(mappers.claude({'five_hour': {'utilization': None}}), [])
        self.assertEqual(mappers.ollama({'limits': {'session': {'usage': True}}}), [])
        self.assertEqual(mappers.antigravity({'groups': [{'buckets': [{'bucketId': 'x', 'remainingFraction': float('nan')}]}]}), [])

    def test_codex_weekly_primary_and_multiple_buckets(self):
        lines = mappers.codex(FIXTURES['codex'])
        self.assertEqual(lines[0]['id'], 'weekly')
        self.assertEqual(lines[0]['periodDurationMs'], 604800000)
        self.assertFalse(any(x['id'] == 'session' for x in lines))
        data = {'rateLimitsByLimitId': {'spark': {'secondary': {'usedPercent': 0, 'windowDurationMins': 300}}},
                'rateLimits': {'primary': {'usedPercent': 99}}}
        self.assertEqual(mappers.codex(data)[0]['id'], 'spark.session')
        self.assertEqual(len(mappers.codex(data)), 1)

    def test_claude_extra_usage_cents_and_unknown_window(self):
        lines = mappers.claude(FIXTURES['claude'])
        self.assertEqual((lines[-1]['used'], lines[-1]['limit'], lines[-1]['format']['kind']), (1.25, 20, 'dollars'))
        self.assertEqual(mappers.claude({'extra_usage': {'is_enabled': False, 'used_credits': 9999}}), [])
        self.assertEqual(mappers.claude({'future_window': {'utilization': 0}})[0]['used'], 0)

    def test_copilot_unlimited_and_org_metrics_never_personal_percentage(self):
        self.assertEqual(mappers.copilot({'quota_snapshots': {'chat': {'entitlement': -1, 'remaining': -1}}}), [])
        rows = mappers.copilot_org({'usageItems': [{'product': 'Copilot', 'unitType': 'ai-credits', 'grossQuantity': 300, 'netAmount': 1.5},
                                                 {'product': 'Actions', 'unitType': 'ai-credits', 'grossQuantity': 999}]})
        self.assertEqual([r['numericValue'] for r in rows], [300, 1.5])
        self.assertTrue(all('Organization' in r['label'] and r['type'] == 'text' for r in rows))

    def test_cursor_team_amounts_and_explicit_disabled_plan(self):
        data = {'planUsage': {'limit': 2000, 'remaining': 1500}, 'spendLimitUsage': {'limitType': 'team', 'individualLimit': 1000, 'individualRemaining': 750}}
        rows = mappers.cursor(data)
        self.assertEqual((rows[0]['used'], rows[0]['limit'], rows[0]['format']['kind']), (5, 20, 'dollars'))
        self.assertEqual(rows[1]['used'], 2.5)
        self.assertEqual(mappers.cursor({'enabled': False, 'planUsage': {'totalPercentUsed': 30}}), [])
        self.assertEqual(mappers.cursor_grok({'usesPooledEnterpriseAllowance': True, 'usagePercent': 25}), [])

    def test_devin_proto_defaults_require_evidence_of_period(self):
        rows = mappers.devin({'userStatus': {'planStatus': {'weeklyQuotaResetAtUnix': 1789776000}}})
        self.assertEqual(rows[0]['used'], 100)
        rows = mappers.devin({'userStatus': {'planStatus': {'weeklyQuotaResetAtUnix': 1789776000, 'weeklyQuotaRemainingPercent': None}}})
        self.assertEqual(rows, [])

    def test_grok_proto_default_and_monthly_label(self):
        data = json.loads(json.dumps(FIXTURES['grok']))
        del data['config']['creditUsagePercent']
        self.assertEqual(mappers.grok(data)[0]['used'], 0)
        data['config']['creditUsagePercent'] = None
        with self.assertRaises(ProviderError): mappers.grok(data)
        data['config']['creditUsagePercent'] = 25
        data['config']['currentPeriod']['type'] = 'USAGE_PERIOD_TYPE_MONTHLY'
        self.assertEqual(mappers.grok(data)[0]['id'], 'period')

    def test_openrouter_key_lifetime_is_not_current_limit_usage(self):
        rows = mappers.openrouter(*FIXTURES['openrouter'])
        by_id = {r['id']: r for r in rows}
        self.assertEqual(by_id['keyLimit']['used'], 3)
        self.assertEqual(by_id['balance']['numericValue'], 15)
        self.assertEqual(by_id['today']['numericValue'], 0)
        self.assertEqual(mappers.openrouter({}, {'data': {'usage': 99, 'limit': 10}}), [])

    def test_reset_timestamps_and_ids_reach_renderer(self):
        provider = {'providerId': 'antigravity', 'displayName': 'Antigravity', 'fetchedAt': iso(NOW),
                    'lines': mappers.antigravity(FIXTURES['antigravity'])}
        prefs = settings.direct([provider])
        self.assertEqual(customize.available(provider)[0][0], 'antigravity.geminiPro')
        with patch.dict(os.environ, {'OH_MY_USAGE_CONFIG_DIR': '/nonexistent/omu-test-config'}):
            self.assertIn('Gemini 5h 25%', customize.render_inline([provider], prefs, NOW))
        self.assertEqual(provider['lines'][0]['resetsAt'], RESET)


class IsolatedTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        env = {'HOME': str(self.root), 'PATH': '/nonexistent', 'OH_MY_USAGE_CONFIG_DIR': str(self.root / 'config'),
               'OH_MY_USAGE_CACHE_DIR': str(self.root / 'cache'), 'OH_MY_USAGE_SOURCE': 'direct'}
        for context in (patch.dict(os.environ, env, clear=True), patch.object(Path, 'home', return_value=self.root),
                        patch.object(native.sys, 'platform', 'linux'), patch.object(native.shutil, 'which', return_value=None)):
            context.start()
            self.addCleanup(context.stop)

    def write(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        return path

    def database(self, relative, key, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with contextlib.closing(sqlite3.connect(path)) as db, db:
            db.execute('CREATE TABLE ItemTable (key TEXT, value TEXT)')
            db.execute('INSERT INTO ItemTable VALUES (?, ?)', (key, value))
        return path


class DiscoveryTests(IsolatedTest):
    def test_fresh_linux_home_checks_every_service_without_remote_calls(self):
        with patch.object(native, 'run', return_value=b''), patch.object(Client, 'request', side_effect=AssertionError('network')):
            detected = collector.discover()
        self.assertEqual(set(detected), set(adapters.PROVIDERS))
        self.assertTrue(all(d.credential is None for d in detected.values()))
        self.assertEqual(detected['openrouter'].status, 'api_key_required')

    def test_native_cli_and_editor_stores_are_detected_on_linux(self):
        self.write('.claude/.credentials.json', {'claudeAiOauth': {'accessToken': 'fixture-claude', 'expiresAt': 9999999999999, 'scopes': ['user:profile']}})
        self.write('.config/github-copilot/apps.json', {'github.com:123': {'oauth_token': 'fixture-copilot'}})
        self.database('.config/Cursor/User/globalStorage/state.vscdb', 'cursorAuth/accessToken', 'fixture-cursor')
        self.database('.config/Devin/User/globalStorage/state.vscdb', 'windsurfAuthStatus', json.dumps({'apiKey': 'fixture-devin'}))
        self.write('.grok/auth.json', {'user': {'key': 'fixture-grok'}})
        self.write('.local/share/opencode/auth.json', {'opencode-go': {'key': 'fixture-go'}})
        self.write('.ollama/id_ed25519', 'not-a-real-key')
        self.write('config/credentials.json', {'openrouter': 'fixture-router', 'zai': 'fixture-zai'})
        for id in ('claude', 'copilot', 'cursor', 'devin', 'grok', 'opencode', 'ollama', 'openrouter', 'zai'):
            with self.subTest(provider=id):
                detected = native.detect(id)
                self.assertTrue(detected.credential)
                self.assertEqual(detected.status, 'ready')
                self.assertNotIn('fixture-', repr(detected))

    def test_gh_hosts_never_uses_enterprise_or_other_users_token(self):
        path = self.root / '.config/gh/hosts.yml'
        path.parent.mkdir(parents=True)
        path.write_text('github.example.com:\n    oauth_token: wrong_enterprise\ngithub.com:\n    oauth_token: github_good\n    users:\n        other:\n            oauth_token: wrong_other\n')
        self.assertEqual(native.detect('copilot').credential.token, 'github_good')

    def test_xdg_and_explicit_config_roots(self):
        self.write('xdg/Cursor/User/globalStorage/state.vscdb.fake', {})
        self.database('xdg/Cursor/User/globalStorage/state.vscdb', 'cursorAuth/accessToken', 'fixture')
        with patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.root / 'xdg')}):
            self.assertEqual(native.detect('cursor').credential.token, 'fixture')
        self.write('custom-claude/.credentials.json', {'claudeAiOauth': {'accessToken': 'custom', 'expiresAt': 9999999999999}})
        with patch.dict(os.environ, {'CLAUDE_CONFIG_DIR': str(self.root / 'custom-claude')}):
            self.assertEqual(native.detect('claude').credential.token, 'custom')
        with patch.dict(os.environ, {'OH_MY_USAGE_CACHE_DIR': '', 'XDG_CACHE_HOME': str(self.root / 'xdg-cache')}):
            self.assertEqual(cache_directory(), self.root / 'xdg-cache/oh-my-usage')

    def test_expired_auth_and_broken_optional_config_do_not_block_other_services(self):
        self.write('.claude/.credentials.json', {'claudeAiOauth': {'accessToken': 'old', 'expiresAt': 1}})
        self.assertEqual(native.detect('claude').status, 'login_expired')
        path = self.write('config/credentials.json', {})
        path.write_text('invalid json')
        self.assertEqual(native.detect('openrouter').status, 'credentials_unreadable')
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'new'}):
            self.assertEqual(native.detect('openrouter').credential.token, 'new')

    def test_devin_cli_toml_and_antigravity_process_discovery(self):
        path = self.root / '.local/share/devin/credentials.toml'
        path.parent.mkdir(parents=True)
        path.write_text('windsurf_api_key = "fixture-key"\napi_server_url = "https://server.codeium.com"\n')
        self.assertEqual(native.detect('devin').credential.token, 'fixture-key')
        processes = b'123 /opt/antigravity/bin/language_server --csrf_token=fixture-csrf --https_server_port 0\n124 /bin/sh -c language_server antigravity --csrf_token wrong\n'
        with patch.object(native, 'run', side_effect=[processes, b'n127.0.0.1:1234\nn0.0.0.0:9999\n']):
            self.assertEqual(native.antigravity_servers(), [{'ports': [1234], 'csrf': 'fixture-csrf', 'pid': '123'}])

    def test_keychain_helper_has_a_hard_deadline_and_safe_error(self):
        with patch.object(native.sys, 'platform', 'darwin'), patch.object(native.subprocess, 'run', side_effect=subprocess.TimeoutExpired('secret', 5)):
            with self.assertRaisesRegex(ProviderError, '^keychain_read_timeout$'):
                native.keychain('service')


class CollectorTests(IsolatedTest):
    def detections(self, token='test-secret'):
        return {'claude': Detection(True, Credential('fixture', token), 'ready')}

    def test_auto_connect_new_service_ttl_and_history_are_independent_of_openusage(self):
        root = self.root / 'cache'
        root.mkdir()
        with patch.object(adapters, 'fetch', return_value=mappers.claude(FIXTURES['claude'])) as fetch:
            self.assertEqual(collector.collect(root, now=NOW, detections={}), [])
            result = collector.collect(root, now=NOW+30, detections=self.detections())
            self.assertEqual(result[0]['providerId'], 'claude')
            collector.collect(root, now=NOW+60, detections=self.detections())
            self.assertEqual(fetch.call_count, 1)
            collector.collect(root, now=NOW+330, detections=self.detections())
            self.assertEqual(fetch.call_count, 2)
        self.assertEqual(len(collector.history(root, now=NOW+330)), 2)
        self.assertNotIn('test-secret', (root / 'direct/state.json').read_text())
        self.assertNotIn(b'test-secret', (root / 'direct/history.sqlite3').read_bytes())
        self.assertEqual((root / 'direct/history.sqlite3').stat().st_mode & 0o777, 0o600)

    def test_account_change_and_logout_remove_old_readings_and_history_view(self):
        root = self.root / 'cache'
        with patch.object(adapters, 'fetch', return_value=mappers.claude(FIXTURES['claude'])):
            collector.collect(root, now=NOW, detections=self.detections('old-account'))
        with patch.object(adapters, 'fetch', side_effect=ProviderError('authentication_required')):
            result = collector.collect(root, now=NOW+30, detections=self.detections('new-account'))
        self.assertEqual(result, [])
        self.assertEqual(collector.history(root, now=NOW+30), [])
        self.assertEqual(collector.collect(root, now=NOW+60, detections={}), [])
        self.assertNotIn('snapshot', collector.load(root)['claude'])

    def test_rate_limit_backoff_is_respected_even_with_force_and_failures_are_isolated(self):
        root = self.root / 'cache'
        detected = self.detections()
        detected['zai'] = Detection(True, Credential('fixture', 'other-secret'), 'ready')
        def fetch(id, credential):
            if id == 'claude': raise ProviderError('rate_limited', retry_after=3600)
            return mappers.zai(FIXTURES['zai'])
        with patch.object(adapters, 'fetch', side_effect=fetch) as call:
            result = collector.collect(root, now=NOW, detections=detected)
            self.assertEqual([p['providerId'] for p in result], ['zai'])
            collector.collect(root, now=NOW+60, force=True, detections=detected)
            self.assertEqual(sum(c.args[0] == 'claude' for c in call.call_args_list), 1)
        self.assertEqual(collector.load(root)['claude']['nextAttempt'], NOW+3600)

    def test_same_login_network_failure_keeps_stale_snapshot_but_auth_failure_clears_it(self):
        root = self.root / 'cache'
        with patch.object(adapters, 'fetch', return_value=mappers.claude(FIXTURES['claude'])):
            collector.collect(root, now=NOW, detections=self.detections())
        with patch.object(adapters, 'fetch', side_effect=RuntimeError('token=secret-in-error')):
            result = collector.collect(root, now=NOW+301, detections=self.detections())
        self.assertEqual(result[0]['fetchedAt'], iso(NOW))
        self.assertEqual(result[0]['status'], 'invalid_response')
        self.assertNotIn('secret-in-error', (root / 'direct/state.json').read_text())
        with patch.object(adapters, 'fetch', side_effect=ProviderError('authentication_required')):
            self.assertEqual(collector.collect(root, now=NOW+600, detections=self.detections()), [])

    def test_default_cli_cache_render_and_source_switch_do_not_reuse_legacy_snapshot(self):
        provider = {'providerId': 'claude', 'displayName': 'Claude', 'fetchedAt': iso(NOW), 'lines': mappers.claude(FIXTURES['claude'])}
        with patch.object(collector, 'collect', return_value=[provider]) as collect, patch('oh_my_usage.settings.load', side_effect=AssertionError('legacy prefs')):
            text = cache.refresh(now=NOW)
            self.assertIn('Claude Session 25%', text)
            self.assertEqual(cache.refresh(now=NOW+1), text)
            self.assertEqual(collect.call_count, 1)
            config.save('mode', 'left')
            self.assertIn('75%', cache.refresh(now=NOW+2, offline=True))
            self.assertEqual(collect.call_count, 1)
        root = self.root / 'cache'
        (root / 'usage-source').write_text('openusage')
        with patch.object(collector, 'collect', return_value=[]) as collect:
            text = cache.refresh(now=NOW+3)
            self.assertIn('no connected services', text)
            collect.assert_called_once()

    def test_history_retention(self):
        root = self.root / 'cache'
        with patch.object(adapters, 'fetch', return_value=mappers.claude(FIXTURES['claude'])):
            collector.collect(root, now=NOW-31*86400, detections=self.detections())
            collector.collect(root, now=NOW, detections=self.detections())
        self.assertEqual(len(collector.history(root, days=30, now=NOW)), 1)

    def test_help_and_status_do_not_send_remote_requests(self):
        with patch.object(collector, 'discover', return_value={id: Detection() for id in adapters.PROVIDERS}), \
             patch.object(Client, 'request', side_effect=AssertionError('network')), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(['providers', '--json']), 0)
        statuses = json.loads(output.getvalue())
        self.assertEqual(len(statuses), 11)
        self.assertTrue(all('binding' not in s and 'snapshot' not in s for s in statuses))


class TransportTests(IsolatedTest):
    def test_actual_routes_and_bearer_headers_for_api_providers(self):
        routes = {'claude': 'api.anthropic.com/api/oauth/usage', 'copilot': 'api.github.com/copilot_internal/user',
                  'devin': 'server.codeium.com/exa.seat_management_pb.SeatManagementService/GetUserStatus',
                  'grok': 'cli-chat-proxy.grok.com/v1/billing?format=credits',
                  'opencode': 'opencode.ai/zen/go/v1/usage', 'zai': 'api.z.ai/api/monitor/usage/quota/limit'}
        for provider, route in routes.items():
            with self.subTest(provider=provider):
                client = Mock()
                client.request.return_value = FIXTURES[provider]
                self.assertTrue(adapters.fetch(provider, Credential('fixture', 'test-token'), client))
                self.assertEqual(client.request.call_args.args[0], 'https://' + route)
                arguments = client.request.call_args.kwargs
                self.assertIn('test-token', json.dumps(arguments))
                self.assertNotIn('test-token', client.request.call_args.args[0])

    def test_openrouter_partial_key_response_survives_unavailable_credit_endpoint(self):
        client = Mock()
        client.request.side_effect = [ProviderError('access_denied'), FIXTURES['openrouter'][1]]
        lines = adapters.fetch('openrouter', Credential('fixture', 'test-token'), client)
        self.assertEqual(lines[0]['id'], 'keyLimit')

    def test_cursor_connect_fallback_and_optional_products(self):
        client = Mock()
        client.request.return_value = FIXTURES['cursor']
        client.optional.return_value = {}
        self.assertEqual(adapters.fetch('cursor', Credential('fixture', 't'), client)[0]['used'], 25)
        self.assertTrue(client.request.call_args.args[0].endswith('GetCurrentPeriodUsage'))
        self.assertEqual(client.request.call_args.kwargs['method'], 'POST')
        payload = base64.urlsafe_b64encode(json.dumps({'sub': 'auth0|abc'}).encode()).decode().rstrip('=')
        client.request.side_effect = [ProviderError('http_404'), {'individualUsage': {'plan': {'totalPercentUsed': 20}}}]
        lines = adapters.fetch('cursor', Credential('fixture', 'head.' + payload + '.signature'), client)
        self.assertEqual(lines[0]['used'], 20)
        self.assertIn('abc%3A%3A', client.request.call_args.kwargs['headers']['Cookie'])
        self.assertNotIn('auth0', client.request.call_args.kwargs['headers']['Cookie'])

    def test_antigravity_local_csrf_never_uses_cloud_bearer(self):
        client = Mock()
        client.request.return_value = FIXTURES['antigravity']
        creds = Credential('local', data={'servers': [{'ports': [1234], 'csrf': 'csrf', 'pid': '5'}]})
        self.assertEqual(len(adapters.fetch('antigravity', creds, client)), 4)
        args = client.request.call_args
        self.assertTrue(args.args[0].startswith('https://127.0.0.1:1234/'))
        self.assertNotIn('Authorization', args.kwargs['headers'])
        self.assertEqual(args.kwargs['headers']['x-codeium-csrf-token'], 'csrf')

    def test_ollama_uses_a_verifiable_signature_and_does_not_send_private_key(self):
        try:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        except ImportError:
            self.skipTest('Install requirements.txt to verify Ollama signing')
        key = Ed25519PrivateKey.generate()
        path = self.root / 'id_ed25519'
        private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH, serialization.NoEncryption())
        path.write_bytes(private)
        client = Mock()
        client.request.return_value = FIXTURES['ollama']
        with patch.object(adapters.time, 'time', return_value=NOW):
            lines = adapters.fetch('ollama', Credential('fixture', data={'path': str(path)}), client)
        self.assertEqual(lines[0]['used'], 25)
        auth = client.request.call_args.kwargs['headers']['Authorization']
        public, signature = auth.split(':')
        self.assertEqual(public.encode(), key.public_key().public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH).split()[1])
        key.public_key().verify(base64.b64decode(signature), ('GET,/api/usage?ts=' + str(NOW)).encode())
        self.assertNotIn('PRIVATE', auth)

    def test_opencode_database_only_counts_hosted_assistant_costs_and_deduplicates(self):
        stamp = datetime.now().timestamp()*1000
        for filename in ('opencode.db', 'opencode-other.db'):
            with contextlib.closing(sqlite3.connect(self.root / filename)) as db, db:
                db.execute('CREATE TABLE message (id TEXT, time_created REAL, data TEXT)')
                for id, role, provider, cost in (('a', 'assistant', 'opencode-go', 1.25), ('b', 'assistant', 'anthropic', 99), ('c', 'user', 'opencode', 88)):
                    db.execute('INSERT INTO message VALUES (?, ?, ?)', (id, stamp, json.dumps({'role': role, 'providerID': provider, 'cost': cost})))
        lines = adapters.local_opencode(self.root)
        self.assertEqual(lines[0]['numericValue'], 1.25)
        self.assertEqual(lines[2]['numericValue'], 1.25)

    def test_http_rejects_insecure_remote_and_redirects_and_honors_retry_after(self):
        with self.assertRaisesRegex(ProviderError, 'https_required'):
            Client().request('http://api.example.com/usage')
        for code, expected in ((302, 'http_302'), (401, 'authentication_required'), (429, 'rate_limited')):
            response = Mock(status=code)
            response.read.return_value = b'{"sensitive":"must not escape"}'
            response.getheader.return_value = '120'
            connection = Mock()
            connection.getresponse.return_value = response
            with patch('oh_my_usage.providers.http.http.client.HTTPSConnection', return_value=connection):
                with self.assertRaises(ProviderError) as caught:
                    Client().request('https://api.example.com/usage')
            self.assertEqual(caught.exception.code, expected)
            self.assertNotIn('sensitive', str(caught.exception))
            self.assertEqual(caught.exception.retry_after, 120)
            connection.close.assert_called_once()

    def test_codex_json_rpc_real_subprocess_never_starts_an_inference_turn(self):
        # A tiny executable simulates the server framing and records every request.
        import sys
        script = self.root / 'codex'
        log = self.root / 'rpc.jsonl'
        script.write_text('#!' + sys.executable + '\nimport json,sys\n' +
                          'for line in sys.stdin:\n' +
                          ' m=json.loads(line)\n' +
                          ' with open(' + repr(str(log)) + ',"a") as f: f.write(line)\n' +
                          ' if "id" not in m: continue\n' +
                          ' result={"account":{"type":"chatgpt"}} if m["method"]=="account/read" else ' + repr(FIXTURES['codex']) + '\n' +
                          ' print(json.dumps({"id":m["id"],"result":result}),flush=True)\n')
        script.chmod(0o755)
        lines = adapters.fetch('codex', Credential('fixture', data={'executable': str(script)}))
        self.assertEqual(lines[0]['id'], 'weekly')
        methods = [json.loads(line)['method'] for line in log.read_text().splitlines()]
        self.assertEqual(methods, ['initialize', 'initialized', 'account/read', 'account/rateLimits/read'])
