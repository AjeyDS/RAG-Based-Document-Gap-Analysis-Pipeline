import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Bot, User, ChevronDown, ChevronRight, X } from 'lucide-react';
import { chatWithKB } from '../api/client';

interface Source {
  story_title: string;
  ac_title: string;
  content: string;
  document_title: string;
  similarity_score: number;
  chunk_type: string;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
}

interface ChatPanelProps {
  onClose?: () => void;
}

export function ChatPanel({ onClose }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = { id: Date.now().toString(), role: 'user', content: input.trim() };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
        const response = await chatWithKB(userMessage.content);
        const assistantMessage: Message = {
            id: (Date.now() + 1).toString(),
            role: 'assistant',
            content: response.answer,
            sources: response.sources
        };
        setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
        console.error("Chat request failed:", error);
        setMessages(prev => [...prev, {
            id: (Date.now() + 1).toString(),
            role: 'assistant',
            content: "Sorry, I encountered an error while processing your request."
        }]);
    } finally {
        setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden relative">
      <div className="px-5 py-4 flex items-center justify-between border-b border-gray-200 bg-[#F5F4F1]">
        <div className="flex items-center gap-3">
          <Bot className="w-5 h-5 text-gray-600" />
          <h2 className="text-base font-medium text-gray-900">
            Chat with Knowledge Base
          </h2>
        </div>
        {onClose && (
          <button 
            type="button" 
            onClick={onClose}
            className="p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-200 rounded-md transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-500 gap-4">
            <Bot className="w-12 h-12 text-gray-300" />
            <p className="text-sm font-medium">Ask questions about the uploaded documents.</p>
          </div>
        ) : (
          messages.map((msg) => (
            <ChatMessage key={msg.id} message={msg} />
          ))
        )}
        {isLoading && (
          <div className="flex items-start gap-3">
             <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center shrink-0">
               <Bot className="w-4 h-4 text-blue-600" />
             </div>
             <div className="bg-gray-50 rounded-2xl px-4 py-2 border border-gray-100">
               <Loader2 className="w-4 h-4 animate-spin text-gray-500" />
             </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSubmit} className="p-4 border-t border-gray-200 bg-white">
        <div className="relative flex items-center">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isLoading}
            placeholder="Ask a question..."
            className="w-full pl-4 pr-12 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-colors disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="absolute right-2 p-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </form>
    </div>
  );
}

function ChatMessage({ message }: { message: Message }) {
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const isUser = message.role === 'user';

  return (
    <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} max-w-full`}>
      <div className={`flex items-start gap-3 max-w-[85%] ${isUser ? 'flex-row-reverse' : ''}`}>
        <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${isUser ? 'bg-indigo-100 text-indigo-600' : 'bg-blue-100 text-blue-600'}`}>
          {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
        </div>
        
        <div className="flex flex-col gap-2 min-w-0">
          <div className={`rounded-2xl px-4 py-3 text-[14px] ${
            isUser 
              ? 'bg-blue-600 text-white' 
              : 'bg-white border border-gray-200 text-gray-800'
          }`}>
            <p className="whitespace-pre-wrap">{message.content}</p>
          </div>

          {!isUser && message.sources && message.sources.length > 0 && (
            <div className="mt-1">
              <button 
                onClick={() => setSourcesOpen(!sourcesOpen)}
                className="flex items-center gap-1.5 text-xs font-medium text-gray-500 hover:text-gray-700 transition-colors"
              >
                {sourcesOpen ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                Sources ({message.sources.length})
              </button>
              
              {sourcesOpen && (
                <div className="mt-2 space-y-2 max-w-lg">
                  {message.sources.map((s, idx) => (
                    <div key={`${s.document_title}-${idx}`} className="bg-[#fcfcfa] border border-[#f0f0eb] rounded-lg p-3 text-xs">
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="font-semibold text-gray-700 truncate mr-2" title={s.document_title}>
                          {s.document_title}
                        </span>
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium uppercase ${
                           s.similarity_score > 0.85 ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
                        }`}>
                          {(s.similarity_score * 100).toFixed(1)}% Match
                        </span>
                      </div>
                      <p className="font-medium text-gray-600 truncate mb-1" title={`${s.story_title} > ${s.ac_title}`}>
                        {s.story_title} &middot; {s.ac_title}
                      </p>
                      <p className="text-gray-500 line-clamp-3 leading-relaxed italic">"{s.content}"</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
