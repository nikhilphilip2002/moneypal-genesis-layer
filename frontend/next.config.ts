import path from 'path';
import type { NextConfig } from 'next';

const rawApiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://100.70.118.31:4321/api';
const baseApiUrl = rawApiUrl.replace(/\/api\/?$/, '').replace(/\/$/, '');

const nextConfig: NextConfig = {
    turbopack: {
        root: path.resolve(__dirname),
    },
    async rewrites() {
        return [
            {
                source: '/api/:path*',
                destination: `${baseApiUrl}/api/:path*`,
            },
        ];
    },
};

export default nextConfig;
