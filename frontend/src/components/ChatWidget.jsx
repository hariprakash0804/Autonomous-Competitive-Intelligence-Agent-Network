import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Calendar, Sparkles, X, Download, Image as ImageIcon, Paperclip, Trash2 } from 'lucide-react';
import { useToast } from '../contexts/ToastContext';
import api from '../api/client';

function parseInlineMarkdown(str) {
  if (typeof str !== 'string') return str;
  const parts = [];
  let lastIndex = 0;
  const regex = /(\*\*(.*?)\*\*|【(.*?)】)/g;
  let match;

  while ((match = regex.exec(str)) !== null) {
    if (match.index > lastIndex) {
      parts.push(str.substring(lastIndex, match.index));
    }
    if (match[2] !== undefined) {
      parts.push(<strong key={match.index} className="font-bold text-white">{match[2]}</strong>);
    } else if (match[3] !== undefined) {
      parts.push(
        <span key={match.index} className="inline-block px-1.5 py-0.5 mx-0.5 rounded bg-indigo-500/20 text-indigo-300 text-[10px] font-mono border border-indigo-500/30">
          {match[3]}
        </span>
      );
    }
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < str.length) {
    parts.push(str.substring(lastIndex));
  }

  return parts.length > 0 ? parts : str;
}

function FormattedMessage({ text }) {
  if (!text) return null;

  const cleanText = text.replace(/\u2011/g, '-');
  const blocks = cleanText.split(/\n\n+/);

  return (
    <div className="space-y-3 leading-relaxed text-xs">
      {blocks.map((block, bIdx) => {
        const trimmed = block.trim();
        if (!trimmed) return null;

        // Render Markdown Headings (#, ##, ###)
        if (trimmed.startsWith('#')) {
          const headingText = trimmed.replace(/^#+\s*/, '');
          return (
            <div key={bIdx} className="flex items-center gap-2 pt-1 pb-0.5 border-b border-indigo-500/20">
              <span className="w-1.5 h-3.5 bg-indigo-400 rounded-full" />
              <h4 className="font-bold text-xs text-indigo-300 font-display uppercase tracking-wider">
                {parseInlineMarkdown(headingText)}
              </h4>
            </div>
          );
        }

        const lines = trimmed.split('\n');

        // Render Markdown Tables (| col 1 | col 2 |)
        if (lines.length >= 2 && lines[0].trim().startsWith('|') && lines[0].trim().endsWith('|')) {
          const tableRows = lines
            .map(l => l.split('|').map(c => c.trim()).filter(Boolean))
            .filter(r => r.length > 0 && !r.every(c => c.startsWith('-')));

          if (tableRows.length > 0) {
            const header = tableRows[0];
            const body = tableRows.slice(1);
            return (
              <div key={bIdx} className="my-2 overflow-x-auto rounded-xl border border-white/[0.08] bg-black/20">
                <table className="w-full text-left text-[11px] border-collapse">
                  <thead>
                    <tr className="bg-white/[0.04] text-indigo-300 font-bold border-b border-white/[0.06]">
                      {header.map((h, i) => (
                        <th key={i} className="px-2.5 py-1.5">{parseInlineMarkdown(h)}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {body.map((row, rI) => (
                      <tr key={rI} className="border-b border-white/[0.03] hover:bg-white/[0.02]">
                        {row.map((cell, cI) => (
                          <td key={cI} className="px-2.5 py-1.5 text-slate-300">{parseInlineMarkdown(cell)}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          }
        }

        const isListBlock = lines.every(l => /^\s*[-*•\d+.]\s+/.test(l));

        // Render Bullet Lists
        if (isListBlock) {
          return (
            <ul key={bIdx} className="space-y-1.5 my-1 pl-1">
              {lines.map((line, lIdx) => {
                const itemText = line.replace(/^\s*[-*•\d+.]\s+/, '');
                return (
                  <li key={lIdx} className="flex items-start gap-2 text-slate-200 bg-white/[0.015] hover:bg-white/[0.03] p-1.5 rounded-lg border border-white/[0.02] transition-colors">
                    <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 mt-1.5 shrink-0" />
                    <span className="flex-1">{parseInlineMarkdown(itemText)}</span>
                  </li>
                );
              })}
            </ul>
          );
        }

        return (
          <p key={bIdx} className="text-slate-200">
            {lines.map((line, lIdx) => (
              <span key={lIdx}>
                {parseInlineMarkdown(line)}
                {lIdx < lines.length - 1 && <br />}
              </span>
            ))}
          </p>
        );
      })}
    </div>
  );
}

export default function ChatWidget({ selectedCompetitor, onClose }) {
  const compKey = selectedCompetitor ? selectedCompetitor.id : 'global';
  const memoryStorageKey = `ci_chat_memory_${compKey}`;

  const defaultIntro = {
    sender: 'bot',
    text: `Hello! I'm your Competitive Intelligence RAG Assistant. Ask me anything grounded in competitor data for ${
      selectedCompetitor ? selectedCompetitor.name : 'all tracked competitors'
    }.`,
    citations: [],
    timestamp: new Date().toISOString(),
  };

  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState(() => {
    try {
      const saved = localStorage.getItem(memoryStorageKey);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch (e) {
      console.error('Failed to load chat memory:', e);
    }
    return [defaultIntro];
  });

  const [loading, setLoading] = useState(false);
  const [attachedMedia, setAttachedMedia] = useState(null); // { url, name, type, textContent }
  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);

  // Chat Memory Persistence to LocalStorage
  useEffect(() => {
    try {
      localStorage.setItem(memoryStorageKey, JSON.stringify(messages));
    } catch (e) {
      console.error('Failed to save chat memory:', e);
    }
  }, [messages, memoryStorageKey]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  // Media & Document File Input Handler
  const handleMediaFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const fileName = file.name;
    const isImage = file.type.startsWith('image/');
    const isTextDoc = file.type.includes('text') || file.type.includes('json') || file.type.includes('csv') || fileName.match(/\.(txt|md|json|csv|html)$/i);

    const reader = new FileReader();

    if (isImage) {
      reader.onload = (event) => {
        setAttachedMedia({
          url: event.target?.result,
          name: fileName,
          type: 'image',
          textContent: null,
        });
      };
      reader.readAsDataURL(file);
    } else if (isTextDoc) {
      reader.onload = (event) => {
        setAttachedMedia({
          url: null,
          name: fileName,
          type: 'document',
          textContent: event.target?.result,
        });
      };
      reader.readAsText(file);
    } else {
      // PDF or other binary doc
      reader.onload = (event) => {
        setAttachedMedia({
          url: event.target?.result,
          name: fileName,
          type: 'document',
          textContent: `[Binary Document Attachment: ${fileName} (${Math.round(file.size / 1024)} KB)]`,
        });
      };
      reader.readAsDataURL(file);
    }
  };

  const handleRemoveAttachedMedia = () => {
    setAttachedMedia(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // Chat Transcript Export Handler (Markdown Download)
  const handleExportChat = () => {
    if (!messages || messages.length === 0) return;

    const compName = selectedCompetitor ? selectedCompetitor.name : 'Global Competitors';
    let md = `# Competitive Intelligence Chat Transcript\n`;
    md += `**Target Competitor**: ${compName}\n`;
    md += `**Exported At**: ${new Date().toLocaleString()}\n\n`;

    messages.forEach((msg) => {
      const role = msg.sender === 'user' ? 'User' : 'RAG Assistant';
      md += `### ${role}\n${msg.text}\n\n`;
      if (msg.image_url || msg.media_filename) {
        md += `*Attached Attachment*: [${msg.media_filename || 'Attached File'}] (${msg.media_type || 'media'})\n\n`;
      }
      if (Array.isArray(msg.citations) && msg.citations.length > 0) {
        md += `**Citations**:\n`;
        msg.citations.forEach((c) => {
          md += `- Source: ${c.source_type} (${c.fetched_at}) — ${c.snippet}\n`;
        });
        md += `\n`;
      }
      md += `---\n\n`;
    });

    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `CI_Chat_Transcript_${compName.replace(/\s+/g, '_')}_${new Date().toISOString().slice(0, 10)}.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const toast = useToast();

  const handleClearMemory = async () => {
    const isConfirmed = await toast.confirm({
      title: 'Clear Chat History',
      message: 'Are you sure you want to clear conversation history for this competitor?',
      confirmText: 'Clear Memory',
      type: 'danger',
    });
    if (isConfirmed) {
      setMessages([defaultIntro]);
      localStorage.removeItem(memoryStorageKey);
      toast.info('Chat history cleared', 'Memory Reset');
    }
  };

  const handleSend = async (e) => {
    e.preventDefault();
    if ((!question.trim() && !attachedMedia) || loading) return;

    const currentMedia = attachedMedia;
    const userMsg = {
      sender: 'user',
      text: question,
      image_url: currentMedia?.url,
      media_filename: currentMedia?.name,
      media_type: currentMedia?.type,
      media_content: currentMedia?.textContent,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    const currentQ = question || (currentMedia ? `Analyzed attached file: ${currentMedia.name}` : '');
    setQuestion('');
    setAttachedMedia(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
    setLoading(true);

    // Format chat history for context memory
    const historyPayload = messages
      .filter((m) => m.text)
      .map((m) => ({
        role: m.sender === 'user' ? 'user' : 'assistant',
        content: m.text,
      }));

    try {
      const response = await api.post('/chat/', {
        competitor_id: selectedCompetitor ? selectedCompetitor.id : null,
        question: currentQ,
        chat_history: historyPayload,
        image_url: currentMedia?.url || null,
        media_filename: currentMedia?.name || null,
        media_type: currentMedia?.type || null,
        media_content: currentMedia?.textContent || null,
      });

      const botMsg = {
        sender: 'bot',
        text: response.data.answer,
        citations: response.data.cited_snapshots || [],
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, botMsg]);
    } catch (error) {
      console.error('Chat query error:', error);
      setMessages((prev) => [
        ...prev,
        {
          sender: 'bot',
          text: 'Error processing question. Please check backend connection or try again.',
          citations: [],
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-[#0a0a14]/98 backdrop-blur-2xl rounded-2xl border border-indigo-500/25 shadow-2xl flex flex-col h-[560px] w-full max-w-lg animate-spring-in overflow-hidden"
      style={{ boxShadow: '0 25px 80px -20px rgba(99, 102, 241, 0.3), 0 0 50px rgba(0, 0, 0, 0.8)' }}
    >
      {/* Header */}
      <div className="p-3.5 border-b border-white/[0.04] flex items-center justify-between bg-white/[0.02] rounded-t-2xl">
        <div className="flex items-center gap-2.5">
          <div className="p-2 bg-indigo-500/10 text-indigo-400 rounded-xl signal-pulse border border-indigo-500/15">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h3 className="font-bold text-white text-sm font-display">RAG Intelligence Chat</h3>
            <p className="text-[10px] text-slate-500">
              {selectedCompetitor ? selectedCompetitor.name : 'Global'} • Memory Active
            </p>
          </div>
        </div>

        {/* Action Controls: Export & Clear Memory */}
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={handleExportChat}
            title="Export Chat Transcript (.md)"
            className="p-1.5 text-slate-400 hover:text-indigo-300 hover:bg-white/[0.05] rounded-lg transition-all text-xs flex items-center gap-1"
          >
            <Download className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={handleClearMemory}
            title="Clear Chat Memory"
            className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-white/[0.05] rounded-lg transition-all"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 text-slate-500 hover:text-slate-200 hover:bg-white/[0.05] rounded-lg transition-all duration-200"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Messages List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs">
        {(Array.isArray(messages) ? messages : []).map((msg, index) => (
          <div
            key={index}
            className={`flex gap-2.5 ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
            style={{ '--i': index, animation: 'fade-in-up 0.3s ease both', animationDelay: `${index * 50}ms` }}
          >
            {msg.sender === 'bot' && (
              <div className="w-7 h-7 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/15 flex items-center justify-center flex-shrink-0">
                <Bot className="w-3.5 h-3.5" />
              </div>
            )}

            <div
              className={`max-w-[82%] p-3.5 rounded-2xl transition-all duration-200 ${
                msg.sender === 'user'
                  ? 'bg-gradient-to-br from-indigo-600 to-indigo-700 text-white rounded-br-sm font-medium shadow-lg shadow-indigo-600/20'
                  : 'bg-white/[0.04] border border-white/[0.06] text-slate-200 rounded-bl-sm space-y-2 hover:border-white/[0.1]'
              }`}
            >
              {/* Render Attached Image / Document inside User Message Bubble */}
              {msg.image_url && msg.media_type === 'image' && (
                <div className="mb-2 rounded-lg overflow-hidden border border-white/20 max-w-[220px]">
                  <img src={msg.image_url} alt={msg.media_filename || 'Attached image'} className="w-full h-auto object-cover max-h-40" />
                  {msg.media_filename && (
                    <p className="px-2 py-1 bg-black/40 text-[9px] text-indigo-200 truncate">{msg.media_filename}</p>
                  )}
                </div>
              )}
              {msg.media_filename && msg.media_type !== 'image' && (
                <div className="mb-2 p-2 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-xs text-indigo-200 flex items-center gap-2">
                  <Paperclip className="w-4 h-4 text-indigo-400 shrink-0" />
                  <div className="truncate">
                    <p className="font-mono text-[10px] font-bold text-white truncate">{msg.media_filename}</p>
                    <p className="text-[9px] text-indigo-300">Document Attachment</p>
                  </div>
                </div>
              )}

              {msg.sender === 'user' ? (
                <p className="whitespace-pre-wrap leading-relaxed">{msg.text}</p>
              ) : (
                <FormattedMessage text={msg.text} />
              )}

              {/* Citations */}
              {Array.isArray(msg.citations) && msg.citations.length > 0 && (
                <div className="border-t border-white/[0.06] pt-2 mt-2 space-y-1.5">
                  <p className="text-[9px] font-semibold text-slate-500 uppercase tracking-widest">
                    Cited Snapshots ({msg.citations?.length || 0})
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {(Array.isArray(msg.citations) ? msg.citations : []).map((cite, cIdx) => (
                      <span
                        key={cIdx}
                        title={cite.snippet}
                        style={{ '--i': cIdx }}
                        className="stagger-item bg-indigo-500/[0.08] text-indigo-300 border border-indigo-500/10 text-[10px] px-2 py-0.5 rounded-lg flex items-center gap-1 font-mono transition-all duration-200 hover:bg-indigo-500/15 hover:border-indigo-500/25 cursor-help"
                      >
                        <Calendar className="w-2.5 h-2.5 text-indigo-400" />
                        {new Date(cite.fetched_at).toLocaleDateString()} ({cite.source_type})
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {msg.sender === 'user' && (
              <div className="w-7 h-7 rounded-xl bg-gradient-to-br from-slate-600 to-slate-700 text-slate-200 flex items-center justify-center flex-shrink-0 shadow-md">
                <User className="w-3.5 h-3.5" />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-2 text-indigo-400 text-xs font-mono p-2 bg-indigo-500/5 border border-indigo-500/10 rounded-xl animate-pulse">
            <Sparkles className="w-3.5 h-3.5 animate-spin" />
            Analyzing snapshots & memory context...
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Attached Media / Document Preview */}
      {attachedMedia && (
        <div className="px-4 py-1.5 bg-indigo-500/10 border-t border-indigo-500/20 flex items-center justify-between text-xs text-indigo-200">
          <div className="flex items-center gap-2 truncate">
            {attachedMedia.type === 'image' && attachedMedia.url ? (
              <img src={attachedMedia.url} alt="Thumbnail" className="w-6 h-6 rounded object-cover border border-indigo-400/30" />
            ) : (
              <Paperclip className="w-4 h-4 text-indigo-400 flex-shrink-0" />
            )}
            <span className="font-mono text-[10px] truncate">{attachedMedia.name} ({attachedMedia.type})</span>
          </div>
          <button
            type="button"
            onClick={handleRemoveAttachedMedia}
            className="p-1 hover:bg-indigo-500/20 rounded text-slate-400 hover:text-white"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Quick Prompt Chips */}
      <div className="px-4 py-2 bg-white/[0.01] border-t border-white/[0.04] flex flex-wrap gap-1.5 overflow-x-auto">
        {[
          "What is their tech stack?",
          "What are their pricing tiers?",
          "What are key customer FAQs?",
          "What are our key advantages?",
        ].map((promptText, pIdx) => (
          <button
            key={pIdx}
            type="button"
            onClick={() => setQuestion(promptText)}
            className="px-2.5 py-1 rounded-lg bg-white/[0.03] hover:bg-indigo-500/10 border border-white/[0.06] hover:border-indigo-500/20 text-[10px] text-slate-400 hover:text-indigo-300 font-medium transition-all duration-200"
          >
            {promptText}
          </button>
        ))}
      </div>

      {/* Input Form with Media Attachment Button */}
      <form onSubmit={handleSend} className="p-3 border-t border-white/[0.04] bg-white/[0.02] flex items-center gap-2">
        {/* Hidden File Input */}
        <input
          type="file"
          ref={fileInputRef}
          accept="image/*,.pdf,.txt,.md,.csv,.json,.doc,.docx"
          onChange={handleMediaFileChange}
          className="hidden"
        />

        {/* Media Upload Trigger Button */}
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          title="Attach Image or Document (.pdf, .txt, .md, .csv, .json)"
          className="p-2.5 rounded-xl bg-white/[0.03] hover:bg-indigo-500/15 border border-white/[0.06] hover:border-indigo-500/30 text-slate-400 hover:text-indigo-300 transition-all"
        >
          <Paperclip className="w-4 h-4" />
        </button>

        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={`Ask anything about ${selectedCompetitor ? selectedCompetitor.name : 'competitors'}...`}
          disabled={loading}
          className="flex-1 bg-white/[0.03] border border-white/[0.06] focus:border-indigo-500/50 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none transition-all duration-200 font-sans"
        />

        <button
          type="submit"
          disabled={loading || (!question.trim() && !attachedMedia)}
          className="btn-gradient px-4 py-2.5 rounded-xl font-medium text-xs flex items-center justify-center gap-1.5 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed shadow-md shadow-indigo-600/20 hover:scale-[1.02] active:scale-[0.98]"
        >
          <Send className="w-3.5 h-3.5" />
        </button>
      </form>
    </div>
  );
}