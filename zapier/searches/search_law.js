'use strict';

const perform = async (z, bundle) => {
  const response = await z.request({
    url: `${bundle.authData.api_url}/api/v1/search`,
    method: 'GET',
    params: {
      q: bundle.inputData.q,
      limit: bundle.inputData.limit || 10,
    },
  });
  const data = response.data;
  return Array.isArray(data) ? data : [data];
};

module.exports = {
  key: 'search_law',
  noun: 'Law',
  display: {
    label: 'Search Law',
    description: 'Search Korean laws and regulations.',
  },
  operation: {
    inputFields: [
      {
        key: 'q',
        label: 'Search Query',
        type: 'string',
        required: true,
        helpText: 'Search keyword for laws (in Korean).',
      },
      {
        key: 'limit',
        label: 'Max Results',
        type: 'integer',
        required: false,
        default: '10',
        helpText: 'Maximum number of results (default 10).',
      },
    ],
    perform,
    sample: {
      id: '1',
      name: '근로기준법',
      status: 'OK',
    },
  },
};
