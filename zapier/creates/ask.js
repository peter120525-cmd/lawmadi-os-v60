'use strict';

const perform = async (z, bundle) => {
  const response = await z.request({
    url: `${bundle.authData.api_url}/api/v1/ask`,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: { query: bundle.inputData.query },
  });
  return response.data;
};

module.exports = {
  key: 'ask',
  noun: 'Legal Answer',
  display: {
    label: 'Ask Legal Question',
    description: 'Ask a legal question to Lawmadi OS AI.',
  },
  operation: {
    inputFields: [
      {
        key: 'query',
        label: 'Question',
        type: 'text',
        required: true,
        helpText: 'The legal question to ask (in Korean).',
      },
    ],
    perform,
    sample: {
      status: 'OK',
      answer: '근로기준법 제50조에 따르면...',
      leader: 'L01',
    },
  },
};
