/** @type {import('next').NextConfig} */
const nextConfig = {
  // Allow fetching from any origin for Yahoo Finance
  async headers() {
    return [
      {
        source: '/api/:path*',
        headers: [
          { key: 'Access-Control-Allow-Origin', value: '*' },
        ],
      },
    ];
  },
};

export default nextConfig;
