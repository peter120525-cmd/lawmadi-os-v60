'use strict';

const authentication = require('./authentication');
const askCreate = require('./creates/ask');
const searchLaw = require('./searches/search_law');

module.exports = {
  version: require('./package.json').version,
  platformVersion: require('zapier-platform-core').version,

  authentication,

  beforeRequest: [
    (request, z, bundle) => {
      if (bundle.authData && bundle.authData.api_key) {
        request.headers.Authorization = `Bearer ${bundle.authData.api_key}`;
      }
      return request;
    },
  ],

  creates: {
    [askCreate.key]: askCreate,
  },

  searches: {
    [searchLaw.key]: searchLaw,
  },
};
