'use client'

import { ThemeProvider } from 'next-themes'
import { ReactNode, useEffect, useState } from 'react'

interface ThemeWrapperProps {
  children: ReactNode
}

export default function ThemeWrapper({ children }: ThemeWrapperProps) {
  const [mounted, setMounted] = useState(false)

  // Only render after hydration to prevent mismatch
  useEffect(() => {
    setMounted(true)
  }, [])

  if (!mounted) {
    // Return a fallback that matches the expected structure
    return (
      <div className="min-h-screen">
        {children}
      </div>
    )
  }

  return (
    <ThemeProvider 
      attribute="class" 
      defaultTheme="system"
      enableSystem={true}
      disableTransitionOnChange={false}
    >
      {children}
    </ThemeProvider>
  )
}
