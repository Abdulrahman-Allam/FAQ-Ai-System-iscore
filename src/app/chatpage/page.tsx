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
import { faHouse, faPlus, faBars, faSun, faPaperPlane, faMagnifyingGlass, faLanguage, faThumbsUp, faThumbsDown } from '@fortawesome/free-solid-svg-icons';

// Images
import iscore from '@/images/iscore.png';

// Add the missing formatTime function
const formatTime = (date: Date): string => {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

// Add ChatBoxProps type definition
type ChatBoxProps = {
  resetTrigger: number;
  isArabic: boolean;
  setIsArabic: (value: boolean) => void;
};

// Add session ID generation
const generateSessionId = () => {
  return 'session_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
};

// Bot reply logic with vacation query support
const botReply = async (userMessage: string, isArabic: boolean = true, sessionId: string, isCommonQuestion: boolean = false): Promise<{text: string, questionId: number | null, status: string}> => {
  try {
    const response = await fetch('http://localhost:5000/ask', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ 
        question: userMessage,
        language: isArabic ? 'ar' : 'en',
        session_id: sessionId,
        is_common_question: isCommonQuestion  // NEW: Flag for dropdown clicks
      }),
    });
    
    if (!response.ok) {
      throw new Error('Failed to get response from server');
    }
    
    const data = await response.json();
    
    if (data.answers && data.answers.length > 0) {
      return {
        text: data.answers[0],
        questionId: data.question_id || null,
        status: data.status || 'answered'
      };
    } else {
      return {
        text: isArabic 
          ? 'عذرًا، لم أجد إجابة مناسبة لسؤالك، لقد أرسلنا سؤالك لفريقنا للإجابة عليه في أقرب وقت ممكن.'
          : 'Sorry, I could not find a suitable answer to your question, we sent this question to our team to answer you as soon as possible.',
        questionId: null,
        status: 'pending'
      };
    }
  } catch (error) {
    console.error('Error calling FAQ API:', error);
    return {
      text: isArabic 
        ? 'عذرًا، حدث خطأ في الاتصال بالخادم. تأكد من تشغيل الخادم على المنفذ 5000.'
        : 'Sorry, there was an error connecting to the server. Make sure the server is running on port 5000.',
      questionId: null,
      status: 'error'
    };
  }
};

// Update Message type
type Message = {
  sender: 'user' | 'bot' | 'system';
  text: string;
  timestamp: string;
  questionId?: number | null;
  status?: string;
};

// Add Common Questions Component
function CommonQuestionsDropdown({ isArabic, onQuestionSelect }: { 
  isArabic: boolean; 
  onQuestionSelect: (question: string) => void; 
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [questions, setQuestions] = useState<Array<{id: string, text: string}>>([]);
  const { theme } = useTheme();

  useEffect(() => {
    fetchCommonQuestions();
  }, [isArabic]);

  const fetchCommonQuestions = async () => {
    try {
      const response = await fetch(`http://localhost:5000/common-questions?language=${isArabic ? 'ar' : 'en'}`);
      const data = await response.json();
      setQuestions(data.questions || []);
    } catch (error) {
      console.error('Error fetching common questions:', error);
    }
  };

  const handleQuestionClick = (questionText: string) => {
    onQuestionSelect(questionText);
    setIsOpen(false);
  };

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors duration-200 ${
          theme === 'dark' 
            ? 'bg-gray-700 text-white hover:bg-gray-600' 
            : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
        }`}>
        {isArabic ? 'الأسئلة الموظفين ▼' : 'Employee Specific Questions ▼'}
      </button>

      {isOpen && (
        <div className={`absolute bottom-full mb-2 w-85 rounded-lg shadow-lg border z-10 
          ${theme === 'dark' ? 'bg-gray-800 border-gray-600' : 'bg-white border-gray-200'}
          ${isArabic ? 'right-0.5' : 'left-0.5'}
          `}>
          <div className="p-2">
            <p className={`text-s font-medium mb-2 text-center pb-2 border-b-2  ${
              theme === 'dark' ? 'text-gray-300 border-b-gray-600' : 'text-gray-600 border-b-gray-200'
            }`}>
              {isArabic ? 'اختر سؤال' : 'Select a question'}
            </p>
            {questions.map((question) => (
              <button
                key={question.id}
                onClick={() => handleQuestionClick(question.text)}
                className={`w-full p-2 text-sm rounded hover:transition-colors duration-200 
                  ${theme === 'dark' ? 'hover:bg-gray-700 text-white' : 'hover:bg-gray-100 text-gray-700'}
                  ${isArabic ? 'text-right' : 'text-left'}
                `}>
                {question.text}
              </button>
            ))}
          </div>
        </div>
      )}

    </div>
  );
}

// ChatBox Component with vacation query support
function ChatBox({ resetTrigger, isArabic, setIsArabic }: ChatBoxProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState<string>('');
  const [isTyping, setIsTyping] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<{ [key: number]: 'up' | 'down' | null }>({});
  const [feedbackMessage, setFeedbackMessage] = useState<{ [key: number]: string }>({});
  const [mounted, setMounted] = useState(false);
  const [sessionId] = useState(() => generateSessionId());

  // Fix hydration issue
  useEffect(() => {
    setMounted(true);
  }, []);

  // Initialize chat when component mounts or language changes
  useEffect(() => {
    if (mounted) {
      resetChat();
    }
  }, [resetTrigger, isArabic, mounted]);

  const sendMessage = async (messageText?: string, isCommonQuestion: boolean = false): Promise<void> => {
    const textToSend = messageText || input.trim();
    if (textToSend === '') return;

    const userMsg: Message = {
      sender: 'user',
      text: textToSend,
      timestamp: formatTime(new Date())
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!messageText) setInput('');
    setIsTyping(true);

    try {
      const { text: replyText, questionId, status } = await botReply(textToSend, isArabic, sessionId, isCommonQuestion);
      const reply: Message = {
        sender: 'bot',
        text: replyText,
        timestamp: formatTime(new Date()),
        questionId: questionId,
        status: status
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

  const handleCommonQuestionSelect = (question: string) => {
    sendMessage(question, true);  // Pass true for isCommonQuestion
  };

  // Update the handleFeedback function to use the correct parameter type
  const handleFeedback = async (questionId: number, feedbackType: 'up' | 'down') => {
    const currentFeedback = feedback[questionId];
    const newFeedback = currentFeedback === feedbackType ? null : feedbackType;
    
    setFeedback(prev => ({
      ...prev,
      [questionId]: newFeedback
    }));

    console.log(`Feedback for question ID ${questionId} - ${newFeedback || 'removed'}`);
    
    // Send feedback to database if questionId exists
    if (questionId && newFeedback !== null) {
      try {
        await fetch('http://localhost:5000/feedback', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            question_id: questionId,
            is_good: newFeedback === 'up'
          }),
        });
        
        console.log(`Feedback sent to database: ${newFeedback === 'up' ? 'positive' : 'negative'}`);
        
        // Show feedback message - PERSISTENT (no timeout removal)
        const thankYouMessage = isArabic ? 'شكراً لك على تقييمك!' : 'Thanks for your feedback!';
        setFeedbackMessage(prev => ({
          ...prev,
          [questionId]: thankYouMessage
        }));
        
      } catch (error) {
        console.error('Error sending feedback:', error);
        const errorMessage = isArabic ? 'خطأ في إرسال التقييم' : 'Error sending feedback';
        setFeedbackMessage(prev => ({
          ...prev,
          [questionId]: errorMessage
        }));
        
        // Clear error message after 3 seconds (keep error timeout)
        setTimeout(() => {
          setFeedbackMessage(prev => {
            const newState = { ...prev };
            if (newState[questionId] === errorMessage) {
              delete newState[questionId];
            }
            return newState;
          });
        }, 3000);
      }
    } else if (newFeedback === null) {
      // Only clear feedback message when feedback is completely removed (clicked same button twice)
      setFeedbackMessage(prev => {
        const newState = { ...prev };
        delete newState[questionId];
        return newState;
      });
    }
  };

  const resetChat = (): void => {
    if (!mounted) return;
    
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
        text: isArabic ? 'مرحباً! كيف يمكنني مساعدتك؟' : 'Hello! How can I help you?',
        timestamp: formatTime(new Date())
      }
    ]);
    
    setFeedback({});
    setFeedbackMessage({});
  };

  const { theme } = useTheme();

  if (!mounted) {
    return (
      <div className="flex flex-col h-full justify-center items-center">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full justify-between p-4">
      {/* Chat messages */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-2">
        {messages.map((msg, index) => (
          msg.sender === 'system' ? (
            <div key={index} className="flex justify-center my-4">
              <div className={`text-sm italic
                        ${theme === 'dark' ? 'text-white' : 'text-gray-600'}`}>
                ───────────── {msg.text} ─────────────
              </div>
            </div>
          ) : (
            <div key={index} className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}>
              <div
                className={`max-w-[70%] px-4 py-2 rounded-2xl shadow ${
                  msg.sender === 'user' ? 'bg-[#4f3795] text-white' : 'bg-[#3ec1c7] text-white'
                } ${isArabic ? 'rtl arabic-text' : 'ltr'}`}>
                <p 
                  className={`${isArabic ? 'text-right' : 'text-left'} whitespace-pre-line`}
                >
                  {msg.text}
                </p>
              </div>
              
              {/* Feedback buttons for bot messages only (except vacation queries) */}
              {msg.sender === 'bot' && (
                <div className="flex items-center justify-between mt-2">
                  <div className="flex items-center space-x-2">
                    {/* Only show feedback buttons if there's a question_id (model responses) */}
                    {msg.questionId && (
                      <>
                        <button
                          onClick={() => handleFeedback(msg.questionId!, 'up')}  // Changed from true to 'up'
                          className={`p-1 rounded transition-colors duration-200 ${
                            feedback[msg.questionId!] === 'up'
                              ? 'bg-green-500 text-white'
                              : theme === 'dark' 
                                ? 'hover:bg-gray-600 text-gray-300 hover:text-green-400' 
                                : 'hover:bg-gray-200 text-gray-600 hover:text-green-600'
                          }`}
                          title={isArabic ? 'مفيد' : 'Helpful'}
                        >
                          👍
                        </button>
                        <button
                          onClick={() => handleFeedback(msg.questionId!, 'down')}  // Changed from false to 'down'
                          className={`p-1 rounded transition-colors duration-200 ${
                            feedback[msg.questionId!] === 'down'
                              ? 'bg-red-500 text-white'
                              : theme === 'dark' 
                                ? 'hover:bg-gray-600 text-gray-300 hover:text-red-400' 
                                : 'hover:bg-gray-200 text-gray-600 hover:text-red-600'
                          }`}
                          title={isArabic ? 'غير مفيد' : 'Not helpful'}
                        >
                          👎
                        </button>
                        
                        {/* Show feedback message */}
                        {feedbackMessage[msg.questionId!] && (
                          <span className={`text-xs italic ml-2 ${
                            theme === 'dark' ? 'text-green-400' : 'text-green-600'
                          }`}>
                            {feedbackMessage[msg.questionId!]}
                          </span>
                        )}
                      </>
                    )}
                  </div>
                  
                  {/* Show timestamp */}
                  <span className={`text-xs ${
                    theme === 'dark' ? 'text-gray-400' : 'text-gray-500'
                  }`}>
                    {msg.timestamp}
                  </span>
                </div>
              )}
            </div>
          )
        ))}

        {isTyping && (
          <div className="flex justify-start">
            <div className={`main text-gray-200 px-4 py-2 rounded-2xl max-w-[70%] italic ${
              isArabic ? 'text-right rtl arabic-text' : 'text-left ltr'
            }`}>
              {isArabic ? 'جاري البحث، أرجو الانتظار' : 'Searching, Please Wait'}
            </div>
          </div>
        )}
      </div>

      {/* Input with Common Questions Dropdown */}
      <div className="mt-4 space-y-2">
        {/* Common Questions Dropdown */}
        <div className={`flex ${isArabic ? 'justify-end' : 'justify-start'}`}>
          <CommonQuestionsDropdown 
            isArabic={isArabic} 
            onQuestionSelect={handleCommonQuestionSelect}
          />
        </div>
        
        {/* Input */}
        <div className={`flex items-center rounded-full p-2
                        ${theme === 'dark' ? 'bg-[#4f3795] text-white' : 'bg-[#3ec1c7] text-white'}`}>
          <FontAwesomeIcon className="ml-3 text-white" icon={faMagnifyingGlass}/>
          <input
            type="text"
            placeholder={isArabic ? "ما هو استفسارك" : "Ask About Anything..."}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            className={`flex-1 focus:outline-none focus:ring-0 rounded-full px-4 py-1.5 text-white placeholder-white/70 ${
              isArabic ? 'text-right rtl arabic-text' : 'text-left ltr'
            }`}
          />

          <button onClick={() => sendMessage()} className={`ml-3 bg-white px-4 py-2 rounded-full transition 
                           ${theme === 'dark' ? 'text-[#4f3795] hover:bg-[#3ec1c7] hover:text-white' : 'text-[#3ec1c7] hover:bg-[#4f3795] hover:text-white '}`}>
            <FontAwesomeIcon icon={faPaperPlane}/>
          </button>
        </div>
      </div>
    </div>
  );
}

// Main Page
export default function Home() {
  const router = useRouter();
  const [resetCounter, setResetCounter] = useState(0);
  const [isArabic, setIsArabic] = useState(false);
  const [mounted, setMounted] = useState(false);

  // Fix hydration issue
  useEffect(() => {
    setMounted(true);
  }, []);
  
  const handleReset = () => {
    setResetCounter(prev => prev + 1);
  };

  const toggleLanguage = () => {
    const newLanguage = !isArabic;
    if (typeof window !== 'undefined') {
      localStorage.setItem('isArabic', newLanguage.toString());
    }
    window.location.reload();
  };

  // Load language preference from localStorage on component mount
  useEffect(() => {
    if (mounted && typeof window !== 'undefined') {
      const savedLanguage = localStorage.getItem('isArabic');
      if (savedLanguage !== null) {
        setIsArabic(savedLanguage === 'true');
      }
    }
  }, [mounted]);

  const { theme, setTheme } = useTheme();

  // Don't render until mounted to prevent hydration mismatch
  if (!mounted) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  return (
    <div>
      <div className={`h-screen flex flex-col items-center ${theme === 'dark' ? 'mainDARK' : 'main'}`}>
        <div className="navBar h-[10%] w-[95%] flex flex-row items-center justify-center space-x-18 py-11">
          <div className='left flex gap-10 w-[30%] justify-center'>
            <button type='button' className={`text-2xl ${theme === 'dark' ? 'iconsDARK' : 'icons'}`} onClick={() => router.push('/')}><FontAwesomeIcon icon={faHouse} /></button>
            <button type='button' className={`text-2xl ${theme === 'dark' ? 'iconsDARK' : 'icons'}`} onClick={handleReset}><FontAwesomeIcon icon={faPlus}/></button>
          </div>
          <div className={`middle w-[30%] flex items-center justify-center gap-5
                        ${isArabic ? 'flex-row-reverse' : 'flex-row'}`}>
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