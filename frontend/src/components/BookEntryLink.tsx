import type { ReactNode } from 'react';
import { useBookEntryViewer, type BookEntryReference } from './BookEntryProvider';

interface BookEntryLinkProps {
  entryRef: BookEntryReference;
  children: ReactNode;
  className?: string;
  title?: string;
}

export default function BookEntryLink({
  entryRef,
  children,
  className,
  title = 'Open book entry',
}: BookEntryLinkProps) {
  const { openEntry } = useBookEntryViewer();
  const canOpen = Boolean(entryRef.workKey || entryRef.title);

  if (!canOpen) {
    return <span className={className}>{children}</span>;
  }

  return (
    <button
      type="button"
      className={['book-entry-link', className].filter(Boolean).join(' ')}
      onClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        openEntry(entryRef);
      }}
      title={title}
    >
      {children}
    </button>
  );
}
