import { useEffect, useId, useRef, useState } from 'react';
import { EllipsisVertical, MessageSquareText } from 'lucide-react';

type ChartActionMenuProps = {
  label: string;
  onAttach: () => void;
};

export function ChartActionMenu({ label, onAttach }: ChartActionMenuProps) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const menuId = useId();

  useEffect(() => {
    if (!open) return;

    const closeOnOutsidePress = (event: PointerEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };

    document.addEventListener('pointerdown', closeOnOutsidePress);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('pointerdown', closeOnOutsidePress);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [open]);

  const attach = () => {
    setOpen(false);
    onAttach();
  };

  return (
    <div className="column-menu-wrapper" ref={menuRef}>
      <button
        className="column-menu-btn"
        type="button"
        onClick={() => setOpen((current) => !current)}
        title="Chart actions"
        aria-label={`Chart actions for ${label}`}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
      >
        <EllipsisVertical size={15} />
      </button>
      {open ? (
        <div className="column-menu-dropdown" id={menuId} role="menu">
          <button type="button" role="menuitem" onClick={attach}>
            <MessageSquareText size={14} />
            Add as attachment
          </button>
        </div>
      ) : null}
    </div>
  );
}
