import test from 'node:test';
import assert from 'node:assert/strict';
import {
  planRuntimeEventActions,
  resolveRuntimeLov,
  resolveRuntimeNavigation,
} from '../dist/index.js';

test('event actions are filtered by event and ordered by sequence', () => {
  const actions = [
    { id: 'a2', event: 'CHANGE', action: 'HIDE', targetIds: ['region-1'], sequence: 2 },
    { id: 'a1', event: 'CHANGE', action: 'SHOW', targetIds: ['region-2'], sequence: 1 },
    { id: 'a3', event: 'CLICK', action: 'SUBMIT', targetIds: ['button-1'], sequence: 1 },
  ];
  assert.deepEqual(planRuntimeEventActions('CHANGE', actions, new Set(['region-1', 'region-2'])).map((x) => x.id), ['a1', 'a2']);
});

test('event planner rejects unknown targets and unsupported event/action pairs', () => {
  assert.throws(() => planRuntimeEventActions('PAGE_LOAD', [
    { id: 'a1', event: 'PAGE_LOAD', action: 'SUBMIT', targetIds: ['button'], sequence: 1 },
  ], new Set(['button'])), /not supported/);
  assert.throws(() => planRuntimeEventActions('CHANGE', [
    { id: 'a1', event: 'CHANGE', action: 'SHOW', targetIds: ['missing'], sequence: 1 },
  ], new Set()), /unknown/);
});

test('static LOV supports case-insensitive search, deduplication and max rows', async () => {
  const result = await resolveRuntimeLov({
    id: 'status', source: 'STATIC', searchable: true, maxRows: 2,
    options: [
      { display: 'Draft', value: 'DRAFT' },
      { display: 'Submitted', value: 'SUBMITTED' },
      { display: 'Draft duplicate', value: 'DRAFT' },
      { display: 'Approved', value: 'APPROVED' },
    ],
  }, {}, 'raft');
  assert.deepEqual(result, [{ display: 'Draft', value: 'DRAFT' }, { display: 'Draft duplicate', value: 'DRAFT' }].slice(0, 1));
});

test('provider LOV uses only a registered provider and enforces max rows', async () => {
  const providers = new Map([['departments', {
    async resolve(context, search) {
      assert.equal(context.company, 'KCSI');
      assert.equal(search, 'ops');
      return [{ display: 'Operations', value: 'OPS' }, { display: 'Ops Support', value: 'OPS2' }];
    },
  }]]);
  const result = await resolveRuntimeLov({
    id: 'departments', source: 'PROVIDER', providerId: 'departments', searchable: true, maxRows: 1,
  }, { company: 'KCSI' }, 'ops', providers);
  assert.deepEqual(result, [{ display: 'Operations', value: 'OPS' }]);
});

test('protected navigation is filtered fail-closed and entries are ordered', () => {
  const policy = { id: 'admins', mode: 'ANY_ROLE', roles: ['ADMIN'], message: 'Denied' };
  const entries = [
    { id: 'admin', label: 'Admin', href: '/admin', sequence: 2, public: false, authorizationPolicyId: 'admins' },
    { id: 'home', label: 'Home', href: '/', sequence: 1, public: true },
  ];
  const result = resolveRuntimeNavigation(entries,
    { subject: 'user', roles: ['ADMIN'], authenticated: true }, new Map([['admins', policy]]));
  assert.deepEqual(result.map((x) => x.id), ['home', 'admin']);
  assert.deepEqual(resolveRuntimeNavigation(entries, null, new Map()).map((x) => x.id), ['home']);
});

test('navigation rejects external and protocol-relative destinations', () => {
  assert.throws(() => resolveRuntimeNavigation([
    { id: 'external', label: 'External', href: '//evil.example', sequence: 1, public: true },
  ], null, new Map()), /application-relative/);
});
