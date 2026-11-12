import type { NextConfig } from 'next';

const config: NextConfig = {
  poweredByHeader: false,
  // shared runtime (roadmap R2) ships TypeScript source and is compiled with the application
  transpilePackages: ['@apex2next/runtime-web'],
  async headers() {
    return [{
      source: '/:path*',
      headers: [
        { key: 'X-Frame-Options', value: 'DENY' },
        { key: 'X-Content-Type-Options', value: 'nosniff' },
        { key: 'Referrer-Policy', value: 'same-origin' },
      ],
    }];
  },
};
export default config;
