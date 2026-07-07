/**
 * NEXUS AI TRADING SYSTEM - Root Layout
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This layout provides the root structure for the entire application including:
 * - Global providers (Theme, Auth, WebSocket, API)
 * - Navigation and sidebar
 * - Header and footer
 * - Toast notifications
 * - Modal system
 * - Font loading and optimization
 * - SEO and metadata
 * - Analytics and monitoring
 * - Error boundaries
 * - Suspense boundaries
 * - Service worker registration
 * - PWA support
 * - RTL support
 * - Accessibility features
 * - Performance optimizations
 */

import type { Metadata, Viewport } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import { Analytics } from '@vercel/analytics/react';
import { SpeedInsights } from '@vercel/speed-insights/next';
import { Providers } from '@/components/providers/Providers';
import { Navigation } from '@/components/layout/Navigation';
import { Header } from '@/components/layout/Header';
import { Footer } from '@/components/layout/Footer';
import { ToastContainer } from '@/components/ui/ToastContainer';
import { ModalContainer } from '@/components/ui/ModalContainer';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { Suspense } from 'react';
import { LoadingScreen } from '@/components/ui/LoadingScreen';

// Styles
import './globals.css';

// ============================================
// Font Configuration
// ============================================

const inter = Inter({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-inter',
  weight: ['400', '500', '600', '700', '800', '900'],
  preload: true,
  fallback: ['system-ui', 'arial', 'sans-serif'],
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-jetbrains-mono',
  weight: ['400', '500', '600', '700'],
  preload: true,
  fallback: ['monospace'],
});

// ============================================
// Metadata Configuration
// ============================================

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL || 'https://nexustrading.com'),
  
  // Basic Metadata
  title: {
    default: 'NEXUS AI Trading System - Advanced Algorithmic Trading Platform',
    template: '%s | NEXUS AI Trading',
  },
  description: 'NEXUS AI Trading System is a cutting-edge algorithmic trading platform powered by artificial intelligence. Trade crypto, forex, stocks, and derivatives with advanced AI predictions.',
  
  // Open Graph
  openGraph: {
    title: 'NEXUS AI Trading System',
    description: 'Advanced AI-powered algorithmic trading platform for crypto, forex, stocks, and derivatives.',
    url: process.env.NEXT_PUBLIC_APP_URL,
    siteName: 'NEXUS AI Trading System',
    images: [
      {
        url: '/og-image.jpg',
        width: 1200,
        height: 630,
        alt: 'NEXUS AI Trading System - Advanced Algorithmic Trading Platform',
      },
    ],
    locale: 'en_US',
    type: 'website',
  },
  
  // Twitter Card
  twitter: {
    card: 'summary_large_image',
    title: 'NEXUS AI Trading System',
    description: 'Advanced AI-powered algorithmic trading platform for crypto, forex, stocks, and derivatives.',
    images: ['/twitter-image.jpg'],
    creator: '@NexusTradingIA',
    site: '@NexusTradingIA',
  },
  
  // Icons
  icons: {
    icon: [
      { url: '/favicon.ico' },
      { url: '/favicon-16x16.png', sizes: '16x16', type: 'image/png' },
      { url: '/favicon-32x32.png', sizes: '32x32', type: 'image/png' },
    ],
    apple: [
      { url: '/apple-touch-icon.png', sizes: '180x180', type: 'image/png' },
    ],
    other: [
      { url: '/android-chrome-192x192.png', sizes: '192x192', type: 'image/png' },
      { url: '/android-chrome-512x512.png', sizes: '512x512', type: 'image/png' },
    ],
  },
  
  // Manifest
  manifest: '/manifest.json',
  
  // Verification
  verification: {
    google: process.env.NEXT_PUBLIC_GOOGLE_VERIFICATION,
    yandex: process.env.NEXT_PUBLIC_YANDEX_VERIFICATION,
    yahoo: process.env.NEXT_PUBLIC_YAHOO_VERIFICATION,
  },
  
  // Additional Metadata
  authors: [
    { name: 'NEXUS QUANTUM LTD', url: 'https://nexusquantum.com' },
    { name: 'Dr X...', url: 'https://nexusquantum.com' },
  ],
  creator: 'NEXUS QUANTUM LTD',
  publisher: 'NEXUS QUANTUM LTD',
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-video-preview': -1,
      'max-image-preview': 'large',
      'max-snippet': -1,
    },
  },
  alternates: {
    canonical: process.env.NEXT_PUBLIC_APP_URL,
    languages: {
      'en-US': '/en-US',
      'fr-FR': '/fr-FR',
      'es-ES': '/es-ES',
      'zh-CN': '/zh-CN',
    },
  },
  category: 'Finance',
  classification: 'Trading, AI, Finance, Algorithmic Trading',
  keywords: [
    'AI trading',
    'algorithmic trading',
    'crypto trading',
    'forex trading',
    'stock trading',
    'automated trading',
    'trading bot',
    'AI predictions',
    'NEXUS trading',
    'quantum trading',
    'high-frequency trading',
    'machine learning trading',
  ],
  other: {
    'apple-mobile-web-app-capable': 'yes',
    'apple-mobile-web-app-status-bar-style': 'black-translucent',
    'apple-mobile-web-app-title': 'NEXUS Trading',
    'application-name': 'NEXUS AI Trading System',
    'msapplication-TileColor': '#06b6d4',
    'msapplication-config': '/browserconfig.xml',
    'theme-color': '#0f172a',
  },
};

// ============================================
// Viewport Configuration
// ============================================

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 5,
  userScalable: true,
  viewportFit: 'cover',
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#ffffff' },
    { media: '(prefers-color-scheme: dark)', color: '#0f172a' },
  ],
};

// ============================================
// Component Props
// ============================================

interface RootLayoutProps {
  children: React.ReactNode;
}

// ============================================
// Root Layout Component
// ============================================

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html 
      lang="en" 
      className={`${inter.variable} ${jetbrainsMono.variable}`}
      suppressHydrationWarning
    >
      <head>
        {/* Preconnect to external resources */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link rel="preconnect" href={process.env.NEXT_PUBLIC_API_URL} />
        <link rel="preconnect" href={process.env.NEXT_PUBLIC_WS_URL} />
        
        {/* DNS Prefetch */}
        <link rel="dns-prefetch" href="https://fonts.googleapis.com" />
        <link rel="dns-prefetch" href="https://fonts.gstatic.com" />
        <link rel="dns-prefetch" href={process.env.NEXT_PUBLIC_API_URL} />
        <link rel="dns-prefetch" href={process.env.NEXT_PUBLIC_WS_URL} />
        
        {/* Preload critical assets */}
        <link rel="preload" href="/fonts/inter-var.woff2" as="font" type="font/woff2" crossOrigin="anonymous" />
        <link rel="preload" href="/fonts/jetbrains-mono-var.woff2" as="font" type="font/woff2" crossOrigin="anonymous" />
        <link rel="preload" href="/logo.svg" as="image" />
        
        {/* Security Headers */}
        <meta httpEquiv="Content-Security-Policy" content={`
          default-src 'self';
          script-src 'self' 'unsafe-inline' 'unsafe-eval' https://www.google.com https://www.gstatic.com;
          style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
          font-src 'self' https://fonts.gstatic.com;
          img-src 'self' data: https:;
          connect-src 'self' ${process.env.NEXT_PUBLIC_API_URL} ${process.env.NEXT_PUBLIC_WS_URL} https://api.nexustrading.com wss://api.nexustrading.com;
          frame-src 'self' https://www.google.com;
          object-src 'none';
          base-uri 'self';
          form-action 'self';
          upgrade-insecure-requests;
        `} />
        
        <meta name="referrer" content="strict-origin-when-cross-origin" />
        <meta name="x-ua-compatible" content="IE=edge" />
        
        {/* Service Worker Registration */}
        <script
          dangerouslySetInnerHTML={{
            __html: `
              if ('serviceWorker' in navigator) {
                window.addEventListener('load', function() {
                  navigator.serviceWorker.register('/sw.js').then(
                    function(registration) {
                      console.log('ServiceWorker registration successful');
                    },
                    function(err) {
                      console.log('ServiceWorker registration failed: ', err);
                    }
                  );
                });
              }
            `,
          }}
        />
      </head>
      <body className="min-h-screen bg-gray-900 text-white antialiased">
        <ErrorBoundary>
          <Providers>
            <div className="min-h-screen flex flex-col">
              {/* Skip to main content link - Accessibility */}
              <a
                href="#main-content"
                className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-cyan-500 focus:text-white focus:rounded-lg focus:shadow-lg"
              >
                Skip to main content
              </a>

              {/* Header */}
              <Header />

              {/* Main Layout */}
              <div className="flex flex-1 pt-16">
                {/* Sidebar Navigation */}
                <Navigation />

                {/* Main Content */}
                <main
                  id="main-content"
                  className="flex-1 min-h-screen bg-gray-900 overflow-x-hidden"
                  role="main"
                >
                  <Suspense fallback={<LoadingScreen />}>
                    {children}
                  </Suspense>
                </main>
              </div>

              {/* Footer */}
              <Footer />
            </div>

            {/* Toast Container */}
            <ToastContainer />

            {/* Modal Container */}
            <ModalContainer />
          </Providers>
        </ErrorBoundary>

        {/* Analytics */}
        {process.env.NODE_ENV === 'production' && (
          <>
            <Analytics />
            <SpeedInsights />
          </>
        )}

        {/* Performance Monitoring */}
        {process.env.NODE_ENV === 'production' && (
          <script
            dangerouslySetInnerHTML={{
              __html: `
                // Performance monitoring
                if (window.performance) {
                  const observer = new PerformanceObserver((list) => {
                    for (const entry of list.getEntries()) {
                      if (entry.entryType === 'navigation') {
                        console.log('Page load time:', entry.loadEventEnd - entry.startTime, 'ms');
                      }
                    }
                  });
                  observer.observe({ entryTypes: ['navigation'] });
                }

                // Error tracking
                window.addEventListener('error', function(e) {
                  console.error('Global error:', e.error || e.message);
                });

                // Unhandled promise rejection tracking
                window.addEventListener('unhandledrejection', function(e) {
                  console.error('Unhandled promise rejection:', e.reason);
                });
              `,
            }}
          />
        )}
      </body>
    </html>
  );
}

// ============================================
// Export metadata for Next.js
// ============================================

export { metadata, viewport };
