import React, { useState } from 'react';
import { Send, Bot, User, Calendar, Sparkles, X } from 'lucide-react';
import api from '../api/client';

export default function ChatWidget({ selectedCompetitor, onClose }) {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState([
    {
      sender: 'bot',
      text: `Hello! I am your Autonomous Competitive Intelligence RAG Assistant. Ask me anything grounded in competitor snapshot data for ${
        selectedCompetitor ? selectedCompetitor.name : 'all tracked competitors'
      }.`,
      citations: [],
    },
  ]);
  const [loading, setLoading] = useState(false);

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
    <div className="bg-slate-900 border border-slate-800 rounded-xl shadow-2xl flex flex-col h-[550px] w-full max-w-lg animate-slide-up-panel">
      {/* Header */}
      <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/60 rounded-t-xl">
        <div className="flex items-center gap-2">
          <div className="p-2 bg-indigo-600/20 text-indigo-400 rounded-lg signal-pulse">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h3 className="font-bold text-slate-100 text-sm">Competitive Intelligence RAG Chat</h3>
            <p className="text-[11px] text-slate-400">
              Grounded answers with cited snapshot timestamps ({selectedCompetitor ? selectedCompetitor.name : 'Global'})
            </p>
          </div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 transition-transform duration-200 hover:rotate-90"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* Messages List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs">
        {messages.map((msg, index) => (
          <div
            key={index}
            className={`flex gap-2.5 animate-fade-in-up ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {msg.sender === 'bot' && (
              <div className="w-7 h-7 rounded-full bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 flex items-center justify-center flex-shrink-0">
                <Bot className="w-4 h-4" />
              </div>
            )}

            <div
              className={`max-w-[82%] p-3.5 rounded-2xl transition-shadow duration-200 ${
                msg.sender === 'user'
                  ? 'bg-indigo-600 text-white rounded-br-none font-medium'
                  : 'bg-slate-800/80 border border-slate-700/80 text-slate-200 rounded-bl-none shadow-md space-y-2 hover:border-slate-600'
              }`}
            >
              <p className="whitespace-pre-wrap leading-relaxed">{msg.text}</p>

              {/* Render Cited Snapshot Date Badges */}
              {msg.citations && msg.citations.length > 0 && (
                <div className="border-t border-slate-700/60 pt-2 mt-2 space-y-1">
                  <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                    Cited Snapshots ({msg.citations.length})
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {msg.citations.map((cite, cIdx) => (
                      <span
                        key={cIdx}
                        title={cite.snippet}
                        style={{ '--i': cIdx }}
                        className="stagger-item bg-slate-900 text-indigo-300 border border-indigo-800/80 text-[10px] px-2 py-0.5 rounded flex items-center gap-1 font-mono transition-colors duration-150 hover:bg-indigo-950/60 hover:border-indigo-600"
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
              <div className="w-7 h-7 rounded-full bg-slate-700 text-slate-200 flex items-center justify-center flex-shrink-0">
                <User className="w-4 h-4" />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-2.5 animate-fade-in-up">
            <div className="w-7 h-7 rounded-full bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 flex items-center justify-center flex-shrink-0">
              <Bot className="w-4 h-4" />
            </div>
            <div className="bg-slate-800/80 border border-slate-700/80 rounded-2xl rounded-bl-none px-4 py-3 flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 typing-dot" />
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 typing-dot" />
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 typing-dot" />
              <span className="text-slate-400 text-[11px] italic ml-1">retrieving grounded context...</span>
            </div>
          </div>
        )}
      </div>

      {/* Input Form */}
      <form onSubmit={handleSend} className="p-3 border-t border-slate-800 bg-slate-950/60 rounded-b-xl flex gap-2">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={`Ask about ${selectedCompetitor ? selectedCompetitor.name : 'competitors'}...`}
          className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition-all duration-200"
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white px-3.5 py-2 rounded-lg transition-all duration-200 hover:scale-105 active:scale-95 text-xs font-semibold flex items-center gap-1"
        >
          <Send className="w-3.5 h-3.5" />
        </button>
      </form>
    </div>
  );
}