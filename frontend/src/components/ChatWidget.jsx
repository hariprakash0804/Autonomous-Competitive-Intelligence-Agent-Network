import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Calendar, Sparkles, X } from 'lucide-react';
import api from '../api/client';

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
              <p className="whitespace-pre-wrap leading-relaxed">{msg.text}</p>

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