import React from 'react';
import { Inter } from 'next/font/google';
import { Toaster } from 'react-hot-toast';
import { AnalysisProvider } from '../context/AnalysisContext';
import '../styles/globals.css';
import { Header } from '../components/layout/Header';
const inter = Inter({ subsets: ['latin'] });
export const metadata = {
    title: 'Friction Matcher',
    description: 'Find the gaps between your resume and dream job',
};
export default function RootLayout({ children, }) {
    return (<html lang="en" suppressHydrationWarning>
      <body className={`${inter.className} min-h-screen flex flex-col bg-white dark:bg-[#09090b] text-zinc-900 dark:text-zinc-50 antialiased selection:bg-zinc-900/10 dark:selection:bg-zinc-50/10 transition-colors duration-300`}>
        <AnalysisProvider>
          <Header />
          <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            {children}
          </main>
          <Toaster position="top-right"/>
        </AnalysisProvider>
      </body>
    </html>);
}
