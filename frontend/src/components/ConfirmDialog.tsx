import { useEffect, useRef } from 'react';

type ConfirmDialogProps = {
  title: string;
  message: string;
  eyebrow?: string;
  confirmLabel?: string;
  busyLabel?: string;
  busy?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

export function ConfirmDialog({
  title,
  message,
  eyebrow = 'Please confirm',
  confirmLabel = 'Delete',
  busyLabel = 'Working...',
  busy = false,
  onCancel,
  onConfirm,
}: ConfirmDialogProps) {
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    cancelRef.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !busy) onCancel();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [busy, onCancel]);

  return (
    <div className="app-modal-backdrop" onMouseDown={() => !busy && onCancel()}>
      <div
        className="app-modal"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-message"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="app-modal-copy">
          <span className="app-modal-eyebrow">{eyebrow}</span>
          <h3 id="confirm-dialog-title">{title}</h3>
          <p id="confirm-dialog-message">{message}</p>
        </div>
        <div className="app-modal-actions">
          <button ref={cancelRef} type="button" className="app-modal-cancel" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button type="button" className="app-modal-danger" onClick={onConfirm} disabled={busy}>
            {busy ? busyLabel : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
