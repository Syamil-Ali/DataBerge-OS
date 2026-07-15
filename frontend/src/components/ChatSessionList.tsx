import { useEffect, useRef, useState } from 'react';
import { MessageSquare, Plus, Trash2 } from 'lucide-react';
import { ChatSession, deleteChatSession, listChatSessions } from '../services/api';

type ChatSessionListProps = {
  projectId: string;
  datasetId: string;
  activeSessionId: string | null;
  onSessionSelect: (session: ChatSession) => void;
  onNewChat: () => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
};

export function ChatSessionList({
  projectId,
  datasetId,
  activeSessionId,
  onSessionSelect,
  onNewChat,
  collapsed,
  onToggleCollapse,
}: ChatSessionListProps) {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const hasAutoSelectedRef = useRef(false);

  const load = async () => {
    try {
      const data = await listChatSessions(projectId, datasetId);
      setSessions(data);
      if (!activeSessionId && !hasAutoSelectedRef.current) {
        const latestConversation = data.find((session) => session.message_count > 0);
        if (latestConversation) {
          hasAutoSelectedRef.current = true;
          onSessionSelect(latestConversation);
        }
      }
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    hasAutoSelectedRef.current = false;
    if (projectId && datasetId) load();
  }, [projectId, datasetId]);

  // Refresh when activeSessionId changes (new message sent)
  useEffect(() => {
    if (activeSessionId) load();
  }, [activeSessionId]);

  const visibleSessions = sessions.filter((session) => (
    session.message_count > 0 || session.id === activeSessionId
  ));

  const handleDelete = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    try {
      await deleteChatSession(projectId, sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      if (activeSessionId === sessionId) {
        onNewChat();
      }
    } catch {
      // ignore
    }
  };

  const timeAgo = (dateStr: string) => {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'now';
    if (mins < 60) return `${mins}m`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h`;
    const days = Math.floor(hours / 24);
    return `${days}d`;
  };

  if (collapsed) {
    return (
      <div className="session-list-collapsed">
        <button className="session-toggle-btn" onClick={onToggleCollapse} title="Show sessions">
          &rsaquo;
        </button>
        <button className="session-new-btn-collapsed" onClick={onNewChat} title="New Chat">
          +
        </button>
        {visibleSessions.map((s) => (
          <button
            key={s.id}
            className={`session-item-collapsed ${s.id === activeSessionId ? 'active' : ''}`}
            onClick={() => onSessionSelect(s)}
            title={s.title}
          >
            <MessageSquare size={14} />
          </button>
        ))}
      </div>
    );
  }

  return (
    <div className="session-list">
      <div className="session-list-header">
        <button className="session-toggle-btn" onClick={onToggleCollapse} title="Hide sessions">
          ‹
        </button>
        <button className="session-new-btn" onClick={onNewChat}>
          <Plus size={14} />
          <span>New Chat</span>
        </button>
      </div>
      <div className="session-list-items">
        {visibleSessions.map((s) => (
          <div
            key={s.id}
            className={`session-item ${s.id === activeSessionId ? 'active' : ''}`}
            onClick={() => onSessionSelect(s)}
          >
            <MessageSquare size={14} className="session-icon" />
            <div className="session-info">
              <span className="session-title">{s.title}</span>
              <span className="session-meta">
                {timeAgo(s.updated_at)} · {s.message_count} msgs
              </span>
            </div>
            <button
              className="session-delete"
              onClick={(e) => handleDelete(e, s.id)}
              title="Delete chat"
            >
              <Trash2 size={12} />
            </button>
          </div>
        ))}
        {visibleSessions.length === 0 && (
          <div className="session-empty">No conversations yet</div>
        )}
      </div>
    </div>
  );
}
