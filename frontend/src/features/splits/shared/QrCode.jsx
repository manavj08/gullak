import { useEffect, useState } from 'react';

// Renders a scannable QR code for a UPI payment link. `qrcode` is dynamically
// imported so it's only pulled into the bundle when a QR is actually opened.
export default function QrCode({ value, size = 200 }) {
  const [dataUrl, setDataUrl] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setDataUrl(null);
    setFailed(false);
    import('qrcode')
      .then((QRCode) => QRCode.toDataURL(value, { width: size, margin: 1 }))
      .then((url) => { if (!cancelled) setDataUrl(url); })
      .catch(() => { if (!cancelled) setFailed(true); });
    return () => { cancelled = true; };
  }, [value, size]);

  if (failed) return <p className="split-qr__error">Couldn't generate the QR code.</p>;
  if (!dataUrl) {
    return <div className="split-qr__loading" style={{ width: size, height: size }} aria-busy="true" aria-label="Generating QR code" />;
  }
  return <img src={dataUrl} alt="UPI payment QR code" width={size} height={size} className="split-qr__image" />;
}
