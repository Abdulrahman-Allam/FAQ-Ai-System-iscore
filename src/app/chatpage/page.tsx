"use client";
import Image from 'next/image';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useTheme } from 'next-themes';


// FontAwesome
import { config } from '@fortawesome/fontawesome-svg-core';
import '@fortawesome/fontawesome-svg-core/styles.css';
config.autoAddCss = false;
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faHouse, faPlus, faBars, faSun, faPaperPlane, faMagnifyingGlass, faLanguage } from '@fortawesome/free-solid-svg-icons';

// Images
import iscore from '@/images/iscore.png';



// Message type
type Message = {
  sender: 'user' | 'bot' | 'system';
  text: string;
  timestamp: string;
};

// Utility: Format time
const formatTime = (date: Date): string => {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

// Bot reply logic - updated to call Flask API
const botReply = async (userMessage: string, isArabic: boolean = true): Promise<string> => {
  try {
    const response = await fetch('http://localhost:5000/ask', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ question: userMessage }),
    });
    
    if (!response.ok) {
      throw new Error('Failed to get response from server');
    }
    
    const data = await response.json();
    
    // Return the first answer or a default message
    if (data.answers && data.answers.length > 0) {
      return data.answers[0];
    } else {
      return isArabic 
        ? 'عذرًا، لم أجد إجابة مناسبة لسؤالك حول قوانين العمل المصرية.'
        : 'Sorry, I could not find a suitable answer to your question about Egyptian labor laws.';
    }
  } catch (error) {
    console.error('Error calling FAQ API:', error);
    return isArabic 
      ? 'عذرًا، حدث خطأ في الاتصال بالخادم. تأكد من تشغيل الخادم على المنفذ 5000.'
      : 'Sorry, there was an error connecting to the server. Make sure the server is running on port 5000.';
  }
};

type ChatBoxProps = {
  resetTrigger: number;
  isArabic: boolean;
  setIsArabic: (value: boolean) => void;
};




// ChatBox Component
function ChatBox({ resetTrigger, isArabic, setIsArabic }: ChatBoxProps) {

  useEffect(() => {
    resetChat();
  }, [resetTrigger]); // ← already runs on mount and when resetCounter changes


  const [messages, setMessages] = useState<Message[]>([
    { sender: 'bot', text: isArabic ? 'مرحباً! كيف يمكنني مساعدتك؟' : 'Hello! How can I help you with?', timestamp: formatTime(new Date()) }
  ]);
  const [input, setInput] = useState<string>('');
  const [isTyping, setIsTyping] = useState<boolean>(false);


  
  const sendMessage = async (): Promise<void> => {
    if (input.trim() === '') return;

    const userMsg: Message = {
      sender: 'user',
      text: input,
      timestamp: formatTime(new Date())
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setIsTyping(true);

    try {
      const replyText = await botReply(userMsg.text, isArabic);
      const reply: Message = {
        sender: 'bot',
        text: replyText,
        timestamp: formatTime(new Date())
      };
      setMessages((prev) => [...prev, reply]);
    } catch (error) {
      const errorReply: Message = {
        sender: 'bot',
        text: isArabic ? 'عذرًا، حدث خطأ أثناء معالجة سؤالك.' : 'Sorry, an error occurred while processing your question.',
        timestamp: formatTime(new Date())
      };
      setMessages((prev) => [...prev, errorReply]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>): void => {
    if (e.key === 'Enter') {
      e.preventDefault();
      sendMessage();
    }
  };

  const resetChat = (): void => {

    const now = new Date();
    const formattedDate = now.toLocaleDateString(undefined, {
      weekday: 'short',
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  
    setMessages([
    {
      sender: 'system',
      text: `${formattedDate}`,
      timestamp: formatTime(now)
    },
    {
      sender: 'bot',
      text: isArabic ? 'مرحباً! كيف يمكنني مساعدتك؟' : 'Hello! How can I help you with?',
      timestamp: formatTime(new Date())
    }
  ]);
};

  const { theme, setTheme } = useTheme();
  return (
    <div className="flex flex-col h-full justify-between p-4">
      {/* Chat messages */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-2">
      {messages.map((msg, index) => (
        msg.sender === 'system' ? (
          <div key={index} className="flex justify-center my-4">
            <div className={`text-sm italic
                      ${theme === 'dark' ? 'text-white' : 'text-gray-600'}`}>
              ──────────────────────────────────────── {msg.text} ────────────────────────────────────────
            </div>
          </div>
        ) : (
          <div key={index} className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}>
            <div
              className={`max-w-[70%] px-4 py-2 rounded-2xl shadow 
              ${msg.sender === 'user' ? 'bg-[#4f3795] text-white' : 'bg-[#3ec1c7] text-white'}`}>
              <p>{msg.text}</p>
            </div>
            <p className={`text-xs mt-1 px-2
                      ${theme === 'dark' ? 'text-white' : 'text-gray-600'}`}>
              {msg.timestamp}
            </p>
          </div>
        )
      ))}


        {isTyping && (
          <div className="flex justify-start">
            <div className="main text-gray-200 px-4 py-2 rounded-2xl max-w-[70%] italic">
              {isArabic ? 'جاري البحث في قوانين العمل...' : 'Searching labor laws...'}
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className={`mt-4 flex items-center rounded-full  p-2
                      ${theme === 'dark' ? 'bg-[#4f3795] text-white' : 'bg-[#3ec1c7] text-white'}`}>
        <FontAwesomeIcon className="ml-3 text-white" icon={faMagnifyingGlass}/>
        <input
          type="text"
          placeholder={isArabic ? "اسأل عن قوانين العمل..." : "Ask about labor laws"}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          className="flex-1 focus:outline-none focus:ring-0 rounded-full px-4  py-1.5 text-white" 
        />

        
        <button onClick={sendMessage} className={`ml-3 bg-white px-4 py-2 rounded-full transition 
                         ${theme === 'dark' ? 'text-[#4f3795] hover:bg-[#3ec1c7] hover:text-white' : 'text-[#3ec1c7] hover:bg-[#4f3795] hover:text-white '}`}>
          <FontAwesomeIcon icon={faPaperPlane}/>
        </button>
      </div>
    </div>
  );
}



// Main Page
export default function Home() {

  const router = useRouter(); //to switch between pages

  const [resetCounter, setResetCounter] = useState(0);
  const [isArabic, setIsArabic] = useState(true); // Language state
  
  const handleReset = () => {
    setResetCounter(prev => prev + 1);
  };

  const toggleLanguage = () => {
    setIsArabic(!isArabic);
  };

  const { theme, setTheme } = useTheme();

  return (
    <div>
      <div className={`h-screen flex flex-col items-center ${theme === 'dark' ? 'mainDARK' : 'main'}`}>
        <div className="navBar h-[10%] w-[95%] flex flex-row items-center justify-center space-x-18 py-11">
          <div className='left flex gap-10 w-[30%] justify-center'>
            <button type='button' className={`text-2xl ${theme === 'dark' ? 'iconsDARK' : 'icons'}`} onClick={() => router.push('/')}><FontAwesomeIcon icon={faHouse} /></button>
            <button type='button' className={`text-2xl ${theme === 'dark' ? 'iconsDARK' : 'icons'}`} onClick={handleReset}><FontAwesomeIcon icon={faPlus}/></button>
          </div>
          <div className='middle w-[30%] flex items-center justify-center gap-5'>
            <p className='font-bold text-white text-3xl'>{isArabic ? 'تحدث مع' : 'Chat With'}</p>
            <Image src={iscore} alt="iScore" width={150} />
          </div>
          <div className='right w-[30%] flex justify-center gap-10'>
            <button type='button' className={`text-2xl ${theme === 'dark' ? 'iconsDARK' : 'icons'}`} onClick={toggleLanguage}><FontAwesomeIcon icon={faLanguage}/></button>
            <button type='button' className={`text-2xl ${theme === 'dark' ? 'iconsDARK' : 'icons'}`} onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}><FontAwesomeIcon spin icon={faSun}/></button>
            <button type='button' className={`text-2xl ${theme === 'dark' ? 'iconsDARK' : 'icons'}`}><FontAwesomeIcon icon={faBars}/></button>
          </div>
        </div>

        {/* Chat Section */}
        <div className={`chat h-[83%] w-[90%] rounded-4xl transition-colors duration-300
                      ${theme === 'dark' ? 'bg-gray-800' : 'bg-gray-100'}`}>
          <ChatBox resetTrigger={resetCounter} isArabic={isArabic} setIsArabic={setIsArabic}/>
        </div>


      </div>
    </div>
  );
}