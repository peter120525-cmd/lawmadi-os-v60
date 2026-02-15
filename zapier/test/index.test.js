'use strict';

const zapier = require('zapier-platform-core');
const App = require('../index');

const appTester = zapier.createAppTester(App);
zapier.tools.env.inject();

describe('Authentication', () => {
  it('should have custom auth type', () => {
    expect(App.authentication.type).toBe('custom');
  });

  it('should include api_key and api_url fields', () => {
    const keys = App.authentication.fields.map((f) => f.key);
    expect(keys).toContain('api_key');
    expect(keys).toContain('api_url');
  });
});

describe('beforeRequest middleware', () => {
  it('should add Authorization header', () => {
    const middleware = App.beforeRequest[0];
    const request = { headers: {} };
    const bundle = { authData: { api_key: 'test-key-123' } };
    const result = middleware(request, null, bundle);
    expect(result.headers.Authorization).toBe('Bearer test-key-123');
  });

  it('should not add header without authData', () => {
    const middleware = App.beforeRequest[0];
    const request = { headers: {} };
    const bundle = { authData: {} };
    const result = middleware(request, null, bundle);
    expect(result.headers.Authorization).toBeUndefined();
  });
});

describe('Ask Legal Question (create)', () => {
  it('should have correct key and fields', () => {
    const ask = App.creates.ask;
    expect(ask.key).toBe('ask');
    expect(ask.operation.inputFields[0].key).toBe('query');
    expect(ask.operation.inputFields[0].required).toBe(true);
  });
});

describe('Search Law (search)', () => {
  it('should have correct key and fields', () => {
    const search = App.searches.search_law;
    expect(search.key).toBe('search_law');
    expect(search.operation.inputFields[0].key).toBe('q');
    expect(search.operation.inputFields[0].required).toBe(true);
  });
});
