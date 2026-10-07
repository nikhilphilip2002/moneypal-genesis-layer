'use client';

// The mailbox message + attachment viewer, shared by the main console's email cards.
//
// Clicking a cited message opens this: the reassembled message body, the original
// attachment rendered inline when the browser can (image / PDF / text), and a download for
// everything else. The bytes come from the app's own origin via the API proxy, so a
// colleague on another machine gets the file without the ingestion host being reachable.

import { useEffect, useState } from 'react';
import { Download, FileText, Image as ImageIcon, Mail, Paperclip, X } from 'lucide-react';

import { emailAttachment, type EmailCardSource } from '@/lib/api';

const when = (iso: string | null): string => {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
};

const KB = (bytes: number): string => {
  if (!Number.isFinite(bytes) || bytes <= 0) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

type Attachment = NonNullable<EmailCardSource['attachment']>;

/**
 * Load an attachment's bytes with the auth token and expose them as an object URL.
 *
 * The bytes are fetched here (not pointed at directly) because an <img>/<object>/download
 * subresource does not send an Authorization header, and the route is behind the
 * same-origin proxy. The object URL is revoked when the attachment changes or unmounts.
 */
function useAttachmentPreview(attachment: Attachment | null | undefined) {
  const [preview, setPreview] = useState<{ objectUrl: string; text: string } | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!attachment) {
      setPreview(null);
      setFailed(false);
      return;
    }
    let cancelled = false;
    let objectUrl: string | null = null;
    setPreview(null);
    setFailed(false);
    emailAttachment.fetchBlob(attachment.path)
      .then(async (blob) => {
        objectUrl = URL.createObjectURL(blob);
        const text = attachment.kind === 'text' ? await blob.text() : '';
        if (cancelled) {
          URL.revokeObjectURL(objectUrl);
          return;
        }
        setPreview({ objectUrl, text });
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [attachment]);

  return { preview, failed };
}

export function AttachmentPreview({ source }: { source: EmailCardSource }) {
  const attachment = source.attachment;
  const { preview, failed } = useAttachmentPreview(attachment);

  if (!attachment) return null;

  const download = (
    <a
      href={preview?.objectUrl}
      download={attachment.filename}
      aria-disabled={!preview}
      onClick={(e) => { if (!preview) e.preventDefault(); }}
      className={`inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-[11px] text-foreground transition-colors ${preview ? 'hover:bg-muted' : 'pointer-events-none opacity-50'}`}
    >
      <Download className="size-3" />
      Download
    </a>
  );

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-[11px] text-muted-foreground">
          {attachment.kind === 'image' ? <ImageIcon className="size-3" /> : <FileText className="size-3" />}
          <span className="max-w-[16rem] truncate" title={attachment.filename}>
            {attachment.filename}
          </span>
          {KB(attachment.size) && <span>· {KB(attachment.size)}</span>}
        </span>
        {download}
      </div>

      {failed && (
        <p className="text-xs text-destructive">This attachment could not be loaded.</p>
      )}

      {!failed && attachment.kind === 'image' && (
        preview ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={preview.objectUrl}
            alt={attachment.filename}
            className="max-h-[26rem] w-auto rounded-lg border border-border bg-white object-contain"
          />
        ) : (
          <div className="h-40 w-full animate-pulse rounded-lg border border-border bg-muted/40" />
        )
      )}

      {!failed && attachment.kind === 'pdf' && (
        preview ? (
          <object
            data={preview.objectUrl}
            type="application/pdf"
            className="h-[26rem] w-full rounded-lg border border-border bg-white"
          >
            <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-center text-sm text-muted-foreground">
              <FileText className="size-6" />
              <p>This browser cannot display PDFs inline.</p>
            </div>
          </object>
        ) : (
          <div className="h-[26rem] w-full animate-pulse rounded-lg border border-border bg-muted/40" />
        )
      )}

      {!failed && attachment.kind === 'text' && (
        <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-lg border border-border bg-muted/40 p-3 text-xs leading-6 text-foreground/85">
          {preview?.text || source.chunk_text}
        </pre>
      )}

      {!failed && attachment.kind === 'binary' && (
        <p className="text-xs text-muted-foreground">
          This file type has no inline preview. Use Download to open it.
        </p>
      )}
    </div>
  );
}

export function EmailSourceViewer({ source, onClose }: { source: EmailCardSource; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    // Stop the thread behind from scrolling while the dialog is open.
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = previous;
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label={source.subject || 'Message detail'}
      onClick={onClose}
    >
      <div
        className="my-8 w-full max-w-3xl rounded-2xl border border-border bg-background shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-3 border-b border-border px-5 py-4">
          <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-xl bg-primary/10">
            <Mail className="size-4 text-primary" />
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-semibold leading-5">{source.subject || 'Message'}</h2>
            <p className="mt-0.5 truncate text-xs text-muted-foreground">
              {[source.sender, when(source.date ?? null)].filter(Boolean).join(' · ')}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="max-h-[70vh] space-y-5 overflow-y-auto px-5 py-4">
          {source.body && (
            <section className="space-y-1.5">
              <h3 className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Message</h3>
              <p className="whitespace-pre-wrap rounded-xl border border-border bg-muted/30 px-3.5 py-3 text-sm leading-6 text-foreground/90">
                {source.body}
              </p>
            </section>
          )}

          {source.attachment && (
            <section className="space-y-1.5">
              <h3 className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Attachment</h3>
              <AttachmentPreview source={source} />
            </section>
          )}

          {!source.body && !source.attachment && source.chunk_text && (
            <section className="space-y-1.5">
              <h3 className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Matching text</h3>
              <p className="whitespace-pre-wrap rounded-xl border border-border bg-muted/30 px-3.5 py-3 text-sm leading-6 text-foreground/90">
                {source.chunk_text}
              </p>
            </section>
          )}

          {!source.body && !source.attachment && !source.chunk_text && (
            <p className="text-sm text-muted-foreground">No stored content for this message.</p>
          )}
        </div>
      </div>
    </div>
  );
}

/** A cited message as a clickable row that opens the viewer. */
export function EmailSourceRow({ source, onOpen }: { source: EmailCardSource; onOpen: (s: EmailCardSource) => void }) {
  return (
    <button
      type="button"
      onClick={() => onOpen(source)}
      title="Open this message"
      className="flex w-full items-start gap-2.5 rounded-xl border border-border/70 bg-card/60 px-3 py-2 text-left transition-colors hover:border-primary/40 hover:bg-muted"
    >
      <Mail className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-xs font-medium" title={source.subject ?? ''}>
          {source.subject}
        </p>
        <p className="truncate text-[11px] text-muted-foreground">
          {[source.sender, when(source.date ?? null)].filter(Boolean).join(' · ')}
        </p>
      </div>
      {source.attachment && (
        <span
          className="mt-0.5 inline-flex shrink-0 items-center gap-1 rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] text-primary"
          title={`View ${source.attachment.filename}`}
        >
          <Paperclip className="size-2.5" />
          {source.attachment.kind === 'image' ? 'Image' : source.attachment.kind === 'pdf' ? 'PDF' : 'File'}
        </span>
      )}
    </button>
  );
}
