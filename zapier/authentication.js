'use strict';

const test = async (z, bundle) => {
  const response = await z.request({
    url: `${bundle.authData.api_url}/api/v1/me`,
    method: 'GET',
  });
  return response.data;
};

module.exports = {
  type: 'custom',
  fields: [
    {
      key: 'api_key',
      label: 'API Key',
      type: 'string',
      required: true,
      helpText: 'Your Lawmadi OS API key.',
    },
    {
      key: 'api_url',
      label: 'API URL',
      type: 'string',
      required: true,
      default: 'https://lawmadi-os-v60-uzqkp6kadq-du.a.run.app',
      helpText: 'Base URL of the Lawmadi OS API.',
    },
  ],
  test,
  connectionLabel: 'Lawmadi OS ({{bundle.authData.api_url}})',
};
