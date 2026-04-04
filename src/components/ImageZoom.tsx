"use client";

import { useState } from "react";

interface ImageZoomProps {
  src: string;
  alt: string;
  className?: string;
}

export default function ImageZoom({ src, alt, className = "" }: ImageZoomProps) {
  const [zoomed, setZoomed] = useState(false);

  return (
    <>
      <div
        className={`cursor-zoom-in relative group ${className}`}
        onClick={() => setZoomed(true)}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src}
          alt={alt}
          className="w-full max-h-72 object-contain rounded-xl"
          style={{ backgroundColor: "var(--bg-secondary)" }}
          loading="lazy"
        />
        <div
          className="absolute inset-0 rounded-xl flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
          style={{ backgroundColor: "rgba(0,0,0,0.15)" }}
        >
          <span
            className="rounded-full px-3 py-1.5 text-xs font-medium shadow-lg"
            style={{ backgroundColor: "var(--bg-card)", color: "var(--text-secondary)", opacity: 0.95 }}
          >
            Tap to zoom
          </span>
        </div>
      </div>

      {zoomed && (
        <div className="image-zoom-overlay" onClick={() => setZoomed(false)}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={src} alt={alt} />
          <button
            className="absolute top-4 right-4 w-10 h-10 rounded-full bg-white/20 flex items-center justify-center text-white hover:bg-white/30 transition-colors"
            onClick={() => setZoomed(false)}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
      )}
    </>
  );
}
