import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Calendar, Sparkles, X } from 'lucide-react';
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
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState([
    {
      sender: 'bot',
      text: `Hello! I'm your Competitive Intelligence RAG Assistant. Ask me anything grounded in competitor data for ${
        selectedCompetitor ? selectedCompetitor.name : 'all tracked competitors'
      }.`,
      citations: [],
    },
  ]);
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!question.trim() || loading) return;

    const userMsg = { sender: 'user', text: question };
    setMessages((prev) => [...prev, userMsg]);
    const currentQ = question;
    setQuestion('');
    setLoading(true);

    try {
      const response = await api.post('/chat/', {
        competitor_id: selectedCompetitor ? selectedCompetitor.id : null,
        question: currentQ,
      });

      const botMsg = {
        sender: 'bot',
        text: response.data.answer,
        citations: response.data.cited_snapshots || [],
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
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-[#0a0a14]/98 backdrop-blur-2xl rounded-2xl border border-indigo-500/25 shadow-2xl flex flex-col h-[550px] w-full max-w-lg animate-spring-in overflow-hidden"
      style={{ boxShadow: '0 25px 80px -20px rgba(99, 102, 241, 0.3), 0 0 50px rgba(0, 0, 0, 0.8)' }}
    >
      {/* Header */}
      <div className="p-4 border-b border-white/[0.04] flex items-center justify-between bg-white/[0.02] rounded-t-2xl">
        <div className="flex items-center gap-2.5">
          <div className="p-2 bg-indigo-500/10 text-indigo-400 rounded-xl signal-pulse border border-indigo-500/15">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h3 className="font-bold text-white text-sm font-display">RAG Intelligence Chat</h3>
            <p className="text-[10px] text-slate-500">
              {selectedCompetitor ? selectedCompetitor.name : 'Global'} • Grounded answers
            </p>
          </div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="p-1.5 text-slate-500 hover:text-slate-200 hover:bg-white/[0.05] rounded-lg transition-all duration-200 hover:rotate-90"
          >
            <X className="w-4 h-4" />
          </button>
        )}
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
          <div className="flex items-center gap-2.5 animate-fade-in-up">
            <div className="w-7 h-7 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/15 flex items-center justify-center flex-shrink-0">
              <Bot className="w-3.5 h-3.5" />
            </div>
            <div className="bg-white/[0.04] border border-white/[0.06] rounded-2xl rounded-bl-sm px-4 py-3 flex items-center gap-2.5">
              <span className="w-2 h-2 rounded-full bg-indigo-400 typing-dot" />
              <span className="w-2 h-2 rounded-full bg-indigo-400 typing-dot" />
              <span className="w-2 h-2 rounded-full bg-indigo-400 typing-dot" />
              <span className="text-slate-500 text-[10px] italic ml-1">retrieving context...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Form */}
      <form onSubmit={handleSend} className="p-3 border-t border-white/[0.04] bg-white/[0.02] rounded-b-2xl flex gap-2">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={`Ask about ${selectedCompetitor ? selectedCompetitor.name : 'competitors'}...`}
          className="flex-1 bg-white/[0.03] rounded-xl px-3.5 py-2.5 text-xs text-slate-100 placeholder-slate-600 input-glow transition-all duration-300"
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="btn-gradient disabled:opacity-30 px-4 py-2.5 rounded-xl transition-all duration-200 text-xs font-semibold flex items-center gap-1.5"
        >
          <Send className="w-3.5 h-3.5" />
        </button>
      </form>
    </div>
  );
}