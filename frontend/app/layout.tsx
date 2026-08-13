import type { Metadata } from 'next'
import './globals.css'
import { Toaster } from '@/components/ui/toaster'
import { ThemeProvider } from '@/components/ThemeProvider'
import PWARegister from '@/components/PWARegister'
import type { Viewport } from 'next'

export const metadata: Metadata = {
  title: 'Moneypal — Genesis Intelligence Console',
  description: 'Macro-economic, competitive and regulatory intelligence for GICC leadership — by Moneypal.',
  applicationName: 'Moneypal Genesis',
  manifest: '/manifest.webmanifest',
  appleWebApp: {
    capable: true,
    statusBarStyle: 'default',
    title: 'Moneypal Genesis',
  },
  icons: {
    icon: '/moneypal.png',
    apple: '/moneypal.png',
  },
  formatDetection: { telephone: false },
}

export const viewport: Viewport = {
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#005DAA' },
    { media: '(prefers-color-scheme: dark)', color: '#0E1114' },
  ],
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Poppins:wght@500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"
        />
      </head>
      <body className="font-sans antialiased bg-background text-foreground">

        <ThemeProvider
          attribute="class"
          defaultTheme="light"
          forcedTheme="light"
          disableTransitionOnChange
        >
          {children}
          <Toaster />
        </ThemeProvider>
        <PWARegister />
      </body>
    </html>
  )
}
