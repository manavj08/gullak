export default function GullakMark({ size = 32, color = 'var(--color-block)' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path
        d="M8 26c0-8 6.5-14 15-14 5 0 8 1.8 10 3.5l4-1.5 1 5-3 2.2c.6 1.6 1 3.4 1 5.3 0 1-1 2-2 2h-1v4a2 2 0 0 1-2 2h-3a2 2 0 0 1-2-2v-2h-6v2a2 2 0 0 1-2 2h-3a2 2 0 0 1-2-2v-3.5c-3.2-1.6-5-4.6-5-8.5Z"
        stroke={color}
        strokeWidth="2.4"
        strokeLinejoin="round"
        fill={color}
        fillOpacity="0.08"
      />
      <circle cx="30" cy="21" r="1.6" fill={color} />
      <path d="M20 15.5c-1.5-1.8-1.5-4 0-5.5" stroke={color} strokeWidth="2.2" strokeLinecap="round" />
      <rect x="21" y="21" width="6" height="1.8" rx="0.9" fill={color} />
    </svg>
  );
}
