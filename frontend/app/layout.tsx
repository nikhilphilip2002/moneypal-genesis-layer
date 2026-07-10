import type { Metadata } from 'next'
import './globals.css'
import AppSidebar from '@/components/AppSidebar'
import ConditionalHeader from '@/components/ConditionalHeader'
import { SidebarProvider, SidebarInset } from '@/components/ui/sidebar'
import { Toaster } from '@/components/ui/toaster'
import { ThemeProvider } from '@/components/ThemeProvider'
import PWARegister from '@/components/PWARegister'
import MobileTopNav from '@/components/mobile/MobileTopNav'
import MobileTabBar from '@/components/mobile/MobileTabBar'
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
          <SidebarProvider>
            <AppSidebar />
            <SidebarInset>
              <ConditionalHeader />
              <MobileTopNav />
              <main
                className="flex min-h-0 flex-1 flex-col overflow-y-auto md:overflow-hidden relative pb-[calc(env(safe-area-inset-bottom,0px)+88px)] md:pb-0"
              >
                {children}
              </main>
              <footer className="hidden md:block shrink-0 px-6 py-2 text-center text-[11px] text-muted-foreground/70">
                Powered by Aroha Corporate Intelligence Framework
              </footer>
              <MobileTabBar />
            </SidebarInset>
          </SidebarProvider>
          <Toaster />
        </ThemeProvider>
        <PWARegister />
      </body>
    </html>
  )
}
