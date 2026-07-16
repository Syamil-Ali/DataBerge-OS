import { Fragment, FormEvent, KeyboardEvent, useCallback, useEffect, useRef, useState } from 'react';
import { ArrowRight, Bot, Code, Download, Send, User } from 'lucide-react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';

import { askQuestion, ChatSession, createChatSession, deleteChatMessage, getArtifact, getChatProfileContext, getChatSession } from '../services/api';
import { Artifact, ChatAttachment, ChatResponse, Dataset, Project, ReportDraft } from '../types/domain';
import { ChartBlock } from './ChartBlock';
import { ChatReportCard } from './ChatReportCard';
import { ChatSessionList } from './ChatSessionList';
import { ReportDraftCard } from './ReportDraftCard';
import { ReportPlanCard } from './ReportPlanCard';

type Message = {
  id?: string;
  role: 'user' | 'assistant';
  text: string;
  response?: ChatResponse;
  attachments?: { label: string }[];
  reportPlan?: ChatResponse['report_plan'];
  reportDraft?: ReportDraft | null;
};

type ChatExplorerProps = {
  project: Project | null;
  dataset: Dataset | null;
  onArtifactCreated: () => void | Promise<void>;
  onReportSaved?: () => void;
  onCustomizeReportPlan?: (plan: NonNullable<ChatResponse['report_plan']>) => void;
  onOpenReport?: (artifact: Artifact) => void;
  onSessionChange?: (sessionId: string | null) => void;
  openSessionId?: string | null;
  onOpenSessionConsumed?: () => void;
  attachments?: ChatAttachment[];
  onAttachmentRemove?: (index: number) => void;
  onAttachmentsClear?: () => void;
  maxAttachments?: number;
};

const skillLabel: Record<string, string> = {
  intake: 'Intake',
  profiling: 'Profiler',
  query: 'Query',
  visualization: 'Visualization',
  reporting: 'Report',
  engineering: 'Engineering',
  sequential: 'Sequential',
  parallel: 'Parallel',
};

const agentColor: Record<string, string> = {
  team_manager: '#475569',
  data_analyst: '#2563eb',
  data_engineer: '#f97316',
  report_agent: '#0f766e',
};

const agentLabel: Record<string, string> = {
  team_manager: 'Manager',
  data_analyst: 'Analyst',
  data_engineer: 'Engineer',
  report_agent: 'Reporter',
};

const starterMessages = (): Message[] => [
  { role: 'assistant', text: 'Ask a question about this dataset. I can answer directly, run a calculation, create a chart, or create a report.' },
];

function messagesFromSession(full: { messages?: Array<{ id?: string; role: string; content: string; payload?: any }> }): Message[] {
  const loaded = (full.messages || []).map((msg) => ({
    ...(() => {
      const persistedAttachments = Array.isArray(msg.payload?.attachments)
        ? msg.payload.attachments
          .filter((attachment: any) => attachment && typeof attachment.label === 'string')
          .map((attachment: any) => ({ label: attachment.label }))
        : [];
      const firstLine = msg.content.split('\n', 1)[0];
      const isReportAttachment = firstLine.startsWith('Attached report:');
      const isChartAttachment = firstLine.startsWith('Top values chart:') || firstLine.startsWith('Distribution chart:');
      if (msg.role !== 'user' || persistedAttachments.length > 0) {
        return { text: msg.content, attachments: persistedAttachments.length > 0 ? persistedAttachments : undefined };
      }
      if (!isReportAttachment && !isChartAttachment) {
        return { text: msg.content, attachments: undefined };
      }
      const separator = msg.content.indexOf('\n\n');
      const attachmentName = isReportAttachment
        ? firstLine.replace(/^Attached report:\s*/, '').trim()
        : firstLine.replace(/^(Top values chart|Distribution chart):\s*/, '').trim();
      return {
        text: separator >= 0 ? msg.content.slice(separator + 2) : msg.content,
        attachments: attachmentName
          ? [{ label: isReportAttachment ? `Report: ${attachmentName}` : `Chart: ${attachmentName}` }]
          : undefined,
      };
    })(),
    id: msg.id,
    role: msg.role as 'user' | 'assistant',
    response: msg.role === 'assistant' ? (msg.payload as ChatResponse) : undefined,
    reportPlan: msg.role === 'assistant' ? (msg.payload?.report_plan ?? null) : undefined,
    reportDraft: msg.role === 'assistant' ? (msg.payload?.report_draft ?? null) : undefined,
  }));
  return loaded.length > 0 ? loaded : starterMessages();
}

const REPORT_HANDOFF_MESSAGE = 'I\'ve prepared your customized report structure. Executive Report can now open it for review before content generation.';

function isReportPlanHandoff(message: Message) {
  return Boolean(
    message.reportPlan
    && (message.response?.action === 'plan' || message.response?.action === 'plan_revised'),
  );
}

type SequentialGroup = NonNullable<ChatResponse['sequential_groups']>[number];

function SequentialGroupAnswer({ group }: { group: SequentialGroup }) {
  return (
    <section className={`agent-answer-section ${group.agent}`}>
      <div className="agent-answer-list">
        {group.items.map((item) => (
          <article className="agent-answer-item" key={`${group.agent}-${item.index}`}>
            <h4>{item.question}</h4>
            <div className="markdown-body agent-answer-copy">
              <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
                {item.answer || 'No answer returned.'}
              </Markdown>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

export function ChatExplorer({ project, dataset, onArtifactCreated, onReportSaved, onCustomizeReportPlan, onOpenReport, onSessionChange, openSessionId, onOpenSessionConsumed, attachments = [], onAttachmentRemove, onAttachmentsClear, maxAttachments = 3 }: ChatExplorerProps) {
  const [messages, setMessages] = useState<Message[]>(starterMessages);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [busySessionId, setBusySessionId] = useState<string | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [expandedSql, setExpandedSql] = useState<Set<number>>(new Set());
  const [sessionsCollapsed, setSessionsCollapsed] = useState(false);
  const [exportingProfile, setExportingProfile] = useState(false);
  const [removingMessageId, setRemovingMessageId] = useState<string | null>(null);
  const activeSessionIdRef = useRef<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const updateActiveSession = useCallback((sessionId: string | null) => {
    activeSessionIdRef.current = sessionId;
    setActiveSessionId(sessionId);
  }, []);

  const resizeInput = useCallback(() => {
    const inputEl = inputRef.current;
    if (!inputEl) return;
    inputEl.style.height = 'auto';
    inputEl.style.height = `${Math.min(inputEl.scrollHeight, 160)}px`;
  }, []);

  // Reset when dataset changes
  useEffect(() => {
    setMessages(starterMessages());
    setInput('');
    setBusy(false);
    updateActiveSession(null);
  }, [dataset?.id]);

  // Focus input when attachment arrives
  useEffect(() => {
    if (attachments.length > 0) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [attachments.length]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, busy]);

  useEffect(() => {
    resizeInput();
  }, [input, resizeInput]);

  const refreshReportArtifact = useCallback(async (artifactId: string) => {
    if (!project) return;
    try {
      const artifact = await getArtifact(project.id, artifactId);
      setMessages((current) => current.map((message) => (
        message.response?.artifact?.id === artifactId
          ? { ...message, response: { ...message.response, artifact } }
          : message
      )));
    } catch {
      // Keep the report placeholder visible if the artifact is temporarily unavailable.
    }
  }, [project?.id]);

  useEffect(() => {
    const pendingIds = [...new Set(messages
      .map((message) => message.response?.artifact)
      .filter((artifact): artifact is Artifact => Boolean(artifact && artifact.kind === 'report' && artifact.status === 'generating'))
      .map((artifact) => artifact.id))];
    if (!pendingIds.length) return;
    const poll = () => pendingIds.forEach((artifactId) => { void refreshReportArtifact(artifactId); });
    poll();
    const interval = window.setInterval(poll, 4000);
    return () => window.clearInterval(interval);
  }, [messages, refreshReportArtifact]);

  const handleSessionSelect = async (session: ChatSession) => {
    if (!project) return;
    try {
      const full = await getChatSession(project.id, session.id);
      updateActiveSession(session.id);
      onSessionChange?.(session.id);
      setMessages(messagesFromSession(full));
    } catch {
      // ignore
    }
  };

  const handleNewChat = () => {
    updateActiveSession(null);
    onSessionChange?.(null);
    setMessages(starterMessages());
    setInput('');
  };

  useEffect(() => {
    if (!project || !openSessionId) return;
    let cancelled = false;
    getChatSession(project.id, openSessionId)
      .then((full) => {
        if (cancelled) return;
        updateActiveSession(openSessionId);
        onSessionChange?.(openSessionId);
        setMessages(messagesFromSession(full));
        onOpenSessionConsumed?.();
      })
      .catch(() => {
        if (!cancelled) onOpenSessionConsumed?.();
      });
    return () => { cancelled = true; };
  }, [openSessionId, project?.id]);

  const exportProfileContext = async () => {
    if (!project || !dataset || exportingProfile) return;
    setExportingProfile(true);
    try {
      const context = await getChatProfileContext(project.id, dataset.id);
      const json = JSON.stringify(context, null, 2);
      const blob = new Blob([json], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      const safeName = (dataset.name || dataset.id).replace(/[^a-z0-9-_]+/gi, '_').replace(/^_+|_+$/g, '') || 'dataset';
      link.href = url;
      link.download = `data-profile-context-${safeName}.json`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      setMessages((prev) => [...prev, {
        role: 'assistant',
        text: error instanceof Error ? `Profile export failed: ${error.message}` : 'Profile export failed.',
      }]);
    } finally {
      setExportingProfile(false);
    }
  };

  const removeChatMessage = async (messageId: string) => {
    if (!project || removingMessageId) return;
    setRemovingMessageId(messageId);
    try {
      await deleteChatMessage(project.id, messageId);
      setMessages((current) => current.filter((message) => message.id !== messageId));
    } finally {
      setRemovingMessageId(null);
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!project || !dataset || !input.trim()) return;
    const displayText = input.trim();
    const userQuestion = displayText.slice(0, 2000);
    const question = userQuestion;
    const sentAttachments = attachments.length > 0 ? [...attachments] : undefined;
    if (attachments.length > 0) {
      onAttachmentsClear?.();
    }
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', text: displayText, attachments: sentAttachments }]);
    setBusy(true);

    // Create session immediately on first message so it appears in sidebar
    let currentSessionId = activeSessionId;
    if (!currentSessionId && project && dataset) {
      try {
        const title = displayText.length > 50 ? displayText.slice(0, 47) + '...' : displayText || 'New Chat';
        const session = await createChatSession(project.id, dataset.id, title);
        currentSessionId = session.id;
        updateActiveSession(session.id);
        onSessionChange?.(session.id);
      } catch {
        // If session creation fails, backend will auto-create one
      }
    }

    setBusySessionId(currentSessionId);

    try {
      const response = await askQuestion(project.id, dataset.id, question, currentSessionId || '', sentAttachments || []);
      if (response.session_id && !currentSessionId && !activeSessionIdRef.current) {
        updateActiveSession(response.session_id);
        onSessionChange?.(response.session_id);
      }
      // Only show response if still on the same session
      const responseSessionId = response.session_id || currentSessionId;
      if (responseSessionId === activeSessionIdRef.current) {
        setMessages((prev) => [...prev, {
          id: response.chat_message_id,
          role: 'assistant',
          text: response.answer,
          response,
          reportPlan: response.report_plan ?? null,
          reportDraft: response.report_draft ?? null,
        }]);
      }
      if (response.report_plan && (response.action === 'plan' || response.action === 'plan_revised')) {
        onCustomizeReportPlan?.(response.report_plan);
      }
      if (response.action === 'saved' || response.action === 'queued') {
        await onArtifactCreated();
        onReportSaved?.();
      } else if (response.chart || response.artifact) {
        await onArtifactCreated();
      }
    } catch (error) {
      if (currentSessionId === activeSessionIdRef.current) {
        setMessages((prev) => [...prev, { role: 'assistant', text: error instanceof Error ? error.message : 'Chat failed.' }]);
      }
    } finally {
      setBusy(false);
      setBusySessionId(null);
    }
  };

  const handleInputKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== 'Enter' || event.shiftKey) return;
    event.preventDefault();
    if (!dataset || (busy && busySessionId === activeSessionId) || !input.trim()) return;
    event.currentTarget.form?.requestSubmit();
  };

  const submitReportCommand = (command: string) => {
    setInput(command);
    setTimeout(() => {
      const form = document.querySelector('.chat-input') as HTMLFormElement;
      if (form) form.requestSubmit();
    }, 50);
  };

  const latestReportPlanIndex = messages.reduce(
    (latest, message, index) => message.reportPlan ? index : latest,
    -1,
  );

  const reportPlanWasConfirmed = (index: number) => messages.slice(index + 1).some(
    (message) => message.response?.action === 'queued' || message.response?.action === 'saved',
  );

  return (
    <section className="chat-view">
      <div className="section-title tab-header">
        <div>
          <h2>Explorer</h2>
          <p className="section-subcopy">Ask the data</p>
        </div>
        <div className="header-actions">
          <button
            className="profile-export-btn"
            onClick={exportProfileContext}
            disabled={!project || !dataset || exportingProfile}
            title="Export backend data profile context"
            type="button"
          >
            <Download size={14} />
            <span>{exportingProfile ? 'Exporting' : 'Export profile'}</span>
          </button>
        </div>
      </div>
      <div className="section-divider" />
      <div className="chat-body">
        {project && dataset && (
          <ChatSessionList
            projectId={project.id}
            datasetId={dataset.id}
            activeSessionId={activeSessionId}
            onSessionSelect={handleSessionSelect}
            onNewChat={handleNewChat}
            collapsed={sessionsCollapsed}
            onToggleCollapse={() => setSessionsCollapsed((c) => !c)}
          />
        )}
        <div className="chat-panel">
        <div className="messages">
        {messages.map((message, index) => {
          const reportHandoff = isReportPlanHandoff(message);
          if (message.role === 'assistant' && !reportHandoff && message.response?.mode === 'sequential_batch' && message.response.sequential_groups?.length) {
            return (
              <Fragment key={`${message.role}-${index}`}>
                {message.response.sequential_groups.map((group, groupIndex) => {
                  const color = agentColor[group.agent] || '#08b5cf';
                  const showSql = group.agent === 'data_analyst' && Boolean(message.response?.sql);
                  return (
                    <div className={`message assistant sequential-agent-message ${group.agent}`} key={`${message.role}-${index}-${group.agent}-${groupIndex}`}>
                      <div className="avatar agent-avatar" style={{ background: color }}>
                        <Bot size={15} />
                      </div>
                      <div className="bubble">
                        <div className="message-meta">
                          <span style={{ background: `${color}18`, color }}>
                            {group.label}
                          </span>
                          <span>{group.items.length} question{group.items.length === 1 ? '' : 's'}</span>
                        </div>
                        <SequentialGroupAnswer group={group} />
                        {showSql && (
                          <div className={`sql-block ${expandedSql.has(index) ? 'expanded' : ''}`}>
                            <button className="sql-toggle" onClick={() => {
                              setExpandedSql((prev) => {
                                const next = new Set(prev);
                                if (next.has(index)) next.delete(index);
                                else next.add(index);
                                return next;
                              });
                            }}>
                              <Code size={13} />
                              <span>Queries used</span>
                              <span className="sql-chevron">{expandedSql.has(index) ? 'v' : '>'}</span>
                            </button>
                            {expandedSql.has(index) && (
                              <pre className="sql-code"><code>{message.response?.sql}</code></pre>
                            )}
                          </div>
                        )}
                        {groupIndex === 0 && message.response?.chart && (
                          <ChartBlock title={message.response.chart.title} chart={message.response.chart} data={message.response.data} />
                        )}
                        {groupIndex === 0 && message.reportPlan && !reportHandoff && (
                          <ReportPlanCard
                            plan={message.reportPlan}
                            busy={busy}
                            closed={reportPlanWasConfirmed(index)}
                            onConfirm={index === latestReportPlanIndex && !reportPlanWasConfirmed(index)
                              ? () => submitReportCommand('Confirm this report plan and generate the report')
                              : undefined}
                            onRevise={index === latestReportPlanIndex && !reportPlanWasConfirmed(index)
                              ? (instruction) => submitReportCommand(`Revise the report plan: ${instruction}`)
                              : undefined}
                          />
                        )}
                        {groupIndex === 0 && message.reportDraft && (
                          <ReportDraftCard
                            draft={message.reportDraft}
                            busy={busy}
                            onExecute={() => {
                              setInput('Execute the report');
                              setTimeout(() => {
                                const form = document.querySelector('.chat-input') as HTMLFormElement;
                                if (form) form.requestSubmit();
                              }, 50);
                            }}
                            onRevise={(instruction) => {
                              setInput(`Revise the report: ${instruction}`);
                              setTimeout(() => {
                                const form = document.querySelector('.chat-input') as HTMLFormElement;
                                if (form) form.requestSubmit();
                              }, 50);
                            }}
                          />
                        )}
                      </div>
                    </div>
                  );
                })}
              </Fragment>
            );
          }

          return (
          <div className={`message ${message.role}`} key={`${message.role}-${index}`}>
            <div
              className={`avatar ${message.role === 'assistant' && message.response?.lead_agent ? 'agent-avatar' : ''}`}
              style={message.role === 'assistant' && message.response?.lead_agent
                ? { background: agentColor[message.response.lead_agent] || '#08b5cf' }
                : undefined}
            >
              {message.role === 'user' ? <User size={15} /> : <Bot size={15} />}
            </div>
            <div className="bubble">
              {message.response && (
                <div className="message-meta">
                  {reportHandoff ? (
                    <>
                      <span style={{ background: `${agentColor.report_agent}18`, color: agentColor.report_agent }}>Reporter</span>
                      <span>Report</span>
                    </>
                  ) : message.response.mode === 'sequential_batch' && message.response.sequential_groups?.length ? (
                    <>
                      <span>Multi-agent answer</span>
                      <span>{message.response.sequential_results?.length || 0} questions</span>
                    </>
                  ) : message.response.lead_agent && (
                    <span style={{
                      background: `${agentColor[message.response.lead_agent] || '#08b5cf'}18`,
                      color: agentColor[message.response.lead_agent] || '#08b5cf',
                    }}>
                      {agentLabel[message.response.lead_agent] || message.response.lead_agent}
                    </span>
                  )}
                  {(message.response.mode !== 'sequential_batch' || reportHandoff) && message.response.active_skill && <span>{skillLabel[message.response.active_skill] ?? message.response.active_skill}</span>}
                </div>
              )}
              {message.role === 'assistant' ? (
                <>
                  <div className="markdown-body">
                    <Markdown
                      remarkPlugins={[remarkGfm]}
                      rehypePlugins={[rehypeRaw]}
                      components={{
                        a: ({ children, href }: any) => (
                          <a href={href} target="_blank" rel="noreferrer">
                            {children}
                          </a>
                        ),
                        code: ({ inline, className, children, ...props }: any) => {
                          const text = String(children).trim();
                          const isShort = text.length <= 30 && !text.includes('\n');
                          if (inline || isShort) {
                            return <strong className="inline-word">{children}</strong>;
                          }
                          return (
                            <pre className="markdown-code-block">
                              <code {...props}>{children}</code>
                            </pre>
                          );
                        },
                      }}
                    >
                      {reportHandoff ? REPORT_HANDOFF_MESSAGE : message.text}
                    </Markdown>
                  </div>
                  {reportHandoff && message.reportPlan && onCustomizeReportPlan && (
                    <button
                      type="button"
                      className="report-handoff-action"
                      onClick={() => onCustomizeReportPlan(message.reportPlan!)}
                    >
                      <ArrowRight size={14} />
                      Open Executive Report
                    </button>
                  )}
                </>
              ) : (
                <>
                  {message.attachments && message.attachments.length > 0 && (
                    <div className="message-attachments">
                      {message.attachments.map((att, i) => (
                        <span className="message-attachment-pill" key={i}>
                          <span className="message-attachment-dot" />
                          {att.label}
                        </span>
                      ))}
                    </div>
                  )}
                  <p className="user-message-text">{message.text}</p>
                </>
              )}
              {message.response?.sql && (
                <div className={`sql-block ${expandedSql.has(index) ? 'expanded' : ''}`}>
                  <button className="sql-toggle" onClick={() => {
                    setExpandedSql((prev) => {
                      const next = new Set(prev);
                      if (next.has(index)) next.delete(index);
                      else next.add(index);
                      return next;
                    });
                  }}>
                    <Code size={13} />
                    <span>{message.response.mode === 'sequential_batch' ? 'Queries used' : 'SQL Query'}</span>
                    <span className="sql-chevron">{expandedSql.has(index) ? 'v' : '>'}</span>
                  </button>
                  {expandedSql.has(index) && (
                    <pre className="sql-code"><code>{message.response.sql}</code></pre>
                  )}
                </div>
              )}
              {message.response?.chart && (
                <ChartBlock title={message.response.chart.title} chart={message.response.chart} data={message.response.data} />
              )}
              {message.response?.artifact?.kind === 'report' && (
                <ChatReportCard
                  artifact={message.response.artifact}
                  onOpen={onOpenReport ? () => onOpenReport(message.response!.artifact!) : undefined}
                  onRemove={message.id ? () => { void removeChatMessage(message.id!); } : undefined}
                />
              )}
              {message.reportPlan && !reportHandoff && (
                <ReportPlanCard
                  plan={message.reportPlan}
                  busy={busy}
                  closed={reportPlanWasConfirmed(index)}
                  onConfirm={index === latestReportPlanIndex && !reportPlanWasConfirmed(index)
                    ? () => submitReportCommand('Confirm this report plan and generate the report')
                    : undefined}
                  onRevise={index === latestReportPlanIndex && !reportPlanWasConfirmed(index)
                    ? (instruction) => submitReportCommand(`Revise the report plan: ${instruction}`)
                    : undefined}
                />
              )}
              {message.reportDraft && (
                <ReportDraftCard
                  draft={message.reportDraft}
                  busy={busy}
                  onExecute={() => {
                    setInput('Execute the report');
                    setTimeout(() => {
                      const form = document.querySelector('.chat-input') as HTMLFormElement;
                      if (form) form.requestSubmit();
                    }, 50);
                  }}
                  onRevise={(instruction) => {
                    setInput(`Revise the report: ${instruction}`);
                    setTimeout(() => {
                      const form = document.querySelector('.chat-input') as HTMLFormElement;
                      if (form) form.requestSubmit();
                    }, 50);
                  }}
                />
              )}
            </div>
          </div>
          );
        })}
        {busy && busySessionId === activeSessionId && (
          <div className="message assistant thinking-message">
            <div className="avatar"><Bot size={15} /></div>
            <div className="bubble thinking-bubble">
              <span />
              <span />
              <span />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
        </div>
        {attachments.length > 0 && (
          <div className="chat-attachment-bar">
            <div className="chat-attachment-chips">
              {attachments.map((att, idx) => (
                <div className="chat-attachment-chip" key={`${att.label}-${idx}`}>
                  <span className="chat-attachment-dot" />
                  <span className="chat-attachment-label">{att.label}</span>
                  <button className="chat-attachment-remove" onClick={() => onAttachmentRemove?.(idx)} title="Remove attachment">
                    ×
                  </button>
                </div>
              ))}
            </div>
            {attachments.length < maxAttachments && (
              <span className="chat-attachment-hint">{attachments.length}/{maxAttachments}</span>
            )}
          </div>
        )}
        <form className="chat-input" onSubmit={submit}>
          <textarea
            ref={inputRef}
            value={input}
            onChange={(event) => {
              setInput(event.target.value);
              requestAnimationFrame(resizeInput);
            }}
            onKeyDown={handleInputKeyDown}
            placeholder={dataset ? (attachments.length > 0 ? 'Ask about the attached columns...' : 'Try: top values by category') : 'Upload a dataset first'}
            disabled={!dataset || (busy && busySessionId === activeSessionId)}
            rows={1}
          />
          <button disabled={!dataset || (busy && busySessionId === activeSessionId) || !input.trim()}>
            <Send size={18} />
          </button>
        </form>
        </div>
      </div>
    </section>
  );
}
