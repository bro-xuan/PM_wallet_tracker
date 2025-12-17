'use client';

import Link from 'next/link';

export default function LandingPage() {
  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(180deg, #ff6b9d 0%, #c44569 25%, #f8b500 75%, #ffa500 100%)',
      position: 'relative',
      overflow: 'hidden'
    }}>
      {/* Animated background pattern */}
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundImage: `
          repeating-linear-gradient(90deg, transparent, transparent 2px, rgba(255,255,255,0.03) 2px, rgba(255,255,255,0.03) 4px)
        `,
        pointerEvents: 'none'
      }} />

      {/* Header */}
      <header style={{
        padding: '20px 40px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        background: 'rgba(255, 255, 255, 0.1)',
        backdropFilter: 'blur(10px)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
        position: 'relative',
        zIndex: 10
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{
            padding: '8px 16px',
            background: '#000',
            borderRadius: '20px',
            color: '#fff',
            fontSize: 18,
            fontWeight: 700,
            display: 'flex',
            alignItems: 'center',
            gap: 8
          }}>
            <span>PM</span>
            <span style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: '#27c07d'
            }} />
          </div>
        </div>

        <nav style={{ display: 'flex', alignItems: 'center', gap: 32 }}>
          <a href="#" style={{
            color: '#fff',
            textDecoration: 'none',
            fontSize: 14,
            fontWeight: 500,
            opacity: 0.9,
            display: 'flex',
            alignItems: 'center',
            gap: 4
          }}>
            Resources
            <span style={{ fontSize: 12 }}>▼</span>
          </a>
          <a href="#" style={{
            color: '#fff',
            textDecoration: 'none',
            fontSize: 14,
            fontWeight: 500,
            opacity: 0.9,
            display: 'flex',
            alignItems: 'center',
            gap: 4
          }}>
            Pricing
            <span style={{ fontSize: 12 }}>▼</span>
          </a>
          <Link
            href="/app"
            style={{
              padding: '10px 24px',
              background: 'rgba(255, 255, 255, 0.2)',
              borderRadius: '8px',
              color: '#000',
              textDecoration: 'none',
              fontSize: 14,
              fontWeight: 600,
              border: '1px solid rgba(0, 0, 0, 0.1)',
              transition: 'all 0.2s'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'rgba(255, 255, 255, 0.3)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'rgba(255, 255, 255, 0.2)';
            }}
          >
            Launch App
          </Link>
        </nav>
      </header>

      {/* Hero Section */}
      <main style={{
        position: 'relative',
        zIndex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: 'calc(100vh - 200px)',
        padding: '80px 20px 200px',
        textAlign: 'center'
      }}>
        <h1 style={{
          fontSize: 'clamp(48px, 8vw, 80px)',
          fontWeight: 700,
          color: '#fff',
          margin: 0,
          marginBottom: 24,
          lineHeight: 1.1,
          textShadow: '0 2px 20px rgba(0, 0, 0, 0.2)'
        }}>
          Prediction Market Intel
        </h1>
        <p style={{
          fontSize: 'clamp(20px, 3vw, 28px)',
          color: '#fff',
          margin: 0,
          marginBottom: 48,
          opacity: 0.95,
          fontWeight: 400,
          maxWidth: '800px'
        }}>
          Track all the trades worth attention
        </p>

        <Link
          href="/app"
          style={{
            padding: '16px 32px',
            background: '#fff',
            borderRadius: '8px',
            color: '#000',
            textDecoration: 'none',
            fontSize: 16,
            fontWeight: 600,
            border: '1px solid rgba(0, 0, 0, 0.1)',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            transition: 'all 0.2s',
            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.1)'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'translateY(-2px)';
            e.currentTarget.style.boxShadow = '0 6px 30px rgba(0, 0, 0, 0.15)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'translateY(0)';
            e.currentTarget.style.boxShadow = '0 4px 20px rgba(0, 0, 0, 0.1)';
          }}
        >
          Explore Data
          <span style={{ fontSize: 20 }}>→</span>
        </Link>
      </main>

      {/* Stats Bar */}
      <div style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        padding: '32px 20px',
        background: 'linear-gradient(180deg, rgba(255, 165, 0, 0.4) 0%, rgba(255, 140, 0, 0.5) 100%)',
        backdropFilter: 'blur(10px)',
        borderTop: '1px solid rgba(255, 255, 255, 0.2)',
        display: 'flex',
        justifyContent: 'center',
        gap: 'clamp(24px, 6vw, 80px)',
        flexWrap: 'wrap',
        zIndex: 5
      }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 'clamp(32px, 5vw, 48px)', fontWeight: 700, color: '#fff', marginBottom: 8 }}>
            100+
          </div>
          <div style={{ fontSize: 14, color: 'rgba(255, 255, 255, 0.9)', fontWeight: 500 }}>
            WALLETS TRACKED
          </div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 'clamp(32px, 5vw, 48px)', fontWeight: 700, color: '#fff', marginBottom: 8 }}>
            1M+
          </div>
          <div style={{ fontSize: 14, color: 'rgba(255, 255, 255, 0.9)', fontWeight: 500 }}>
            TRADES MONITORED
          </div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 'clamp(32px, 5vw, 48px)', fontWeight: 700, color: '#fff', marginBottom: 8 }}>
            REAL-TIME
          </div>
          <div style={{ fontSize: 14, color: 'rgba(255, 255, 255, 0.9)', fontWeight: 500 }}>
            LIVE UPDATES
            </div>
            </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 'clamp(32px, 5vw, 48px)', fontWeight: 700, color: '#fff', marginBottom: 8 }}>
            AI READY
          </div>
          <div style={{ fontSize: 14, color: 'rgba(255, 255, 255, 0.9)', fontWeight: 500 }}>
            ADVANCED ANALYTICS
          </div>
        </div>
      </div>
    </div>
  );
}
