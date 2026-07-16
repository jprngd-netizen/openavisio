"use client";

import { useEffect, useState } from "react";

interface Props {
  docId: string;
  contentType: string;
  className?: string;
}

export function DocumentViewer({ docId, contentType, className = "" }: Props) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let url: string | null = null;
    fetch(`/api/documents/${docId}/file`)
      .then((res) => {
        if (!res.ok) throw new Error();
        return res.blob();
      })
      .then((blob) => {
        url = URL.createObjectURL(blob);
        setBlobUrl(url);
      })
      .catch(() => setError(true));
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [docId]);

  if (error) {
    return (
      <div className={`flex items-center justify-center bg-muted rounded-xl text-sm text-muted-foreground ${className}`}>
        Could not load document.
      </div>
    );
  }

  if (!blobUrl) {
    return (
      <div className={`flex items-center justify-center bg-muted rounded-xl text-sm text-muted-foreground animate-pulse ${className}`}>
        Loading…
      </div>
    );
  }

  if (contentType.startsWith("image/")) {
    return (
      <div className={`flex items-center justify-center bg-muted rounded-xl overflow-hidden ${className}`}>
        <img src={blobUrl} alt="Document" className="max-w-full max-h-full object-contain" />
      </div>
    );
  }

  return (
    <iframe
      src={blobUrl}
      className={`block rounded-xl border bg-white ${className}`}
      title="Document"
    />
  );
}
