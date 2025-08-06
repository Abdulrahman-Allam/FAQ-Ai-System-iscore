"use client";
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import { useState } from 'react';

// FontAwesome
import { config } from '@fortawesome/fontawesome-svg-core';
import '@fortawesome/fontawesome-svg-core/styles.css'; // Import the CSS
config.autoAddCss = false; // Prevent FontAwesome from adding its CSS automatically
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faArrowRight, faArrowLeft, faComment, faLanguage } from '@fortawesome/free-solid-svg-icons';

//Images
import iscore from '@/images/iscore.png';
import bot from '@/images/bot.gif';


export default function Home() {
  const router = useRouter(); //to switch between pages
  const [isArabic, setIsArabic] = useState(false); // Language state - Default to English

  const toggleLanguage = () => {
    setIsArabic(!isArabic);
  };

  const goToChatPage = () => {
    // Store language preference before navigating
    localStorage.setItem('isArabic', isArabic.toString());
    router.push('/chatpage');
  };

  return (
    <div className="main h-screen p-15">
      {/* Language Toggle Button */}
      <div className="absolute top-6 right-6 z-10">
        <button 
          onClick={toggleLanguage}
          className="bg-white/20 backdrop-blur text-white px-4 py-2 rounded-full hover:bg-black/30 transition flex items-center gap-2"
        >
          <FontAwesomeIcon icon={faLanguage} />
          {isArabic ? 'English' : 'العربية'}
        </button>
      </div>

      {/* Conditional Layout Based on Language */}
      {isArabic ? (
        // Arabic Layout: Robot on left, content on right
        <div className='flex gap-40 justify-between items-center h-full'>
          <div className='bg-transparent flex-shrink-0'>
            <Image src={bot} alt="iScore" className='' width={400}/>
          </div>
          
          <div className='flex flex-col space-y-14 flex-1 items-end pr-10'> {/* Added items-end and pr-10 for better right alignment */}
            <div className='flex items-center justify-end'> {/* Right align for Arabic */}
              <Image src={iscore} alt="iScore" width={200}/>
              <FontAwesomeIcon bounce className='text-6xl ml-4 text-[#3ec1c7]' icon={faComment}/>
            </div>
            
            {/* Arabic Content */}
            <>
              <div className='text-right w-full'> {/* Added w-full for better alignment */}
                <p className='font-bold text-white text-6xl'>احصل على إجابات فورية</p>
                <p className='font-bold text-white text-6xl'>حول قوانين عمل الشركة</p>
                <p className='font-bold text-[#3ec1c7] text-6xl italic'>الذكي iScore مع مساعد</p>
              </div>

              <div className='text-right w-full'> {/* Added w-full for better alignment */}
                <p className='text-gray-300 text-2xl italic'>يوفر مساعدة فورية في أسئلة قوانين العمل</p>
                <p className='text-gray-300 text-2xl italic'>وحقوق العمال - متاح في أي وقت.</p>
              </div>
              

              <div className='flex justify-end w-full'> {/* Added w-full for consistent alignment */}
                <button 
                  type='button' 
                  className='bg-white rounded-full py-3 font-extrabold w-[60%] text-2xl flex items-center justify-center text-[#4f3795] hover:text-white hover:bg-[#3ec1c7] transition' 
                  onClick={goToChatPage}
                >
                  <FontAwesomeIcon className='pr-6 font-extrabold' fontSize={40} icon={faArrowLeft}/>
                  ! لدي سؤال
                </button>
              </div>
            </>
          </div>
        </div>
      ) : (
        // English Layout: Content on left, robot on right
        <div className='flex gap-40 justify-evenly items-center h-full'>
          <div className='flex flex-col space-y-14 flex-1 pl-10'> {/* Added pl-10 for consistent spacing */}
            <div className='flex items-center'>
              <FontAwesomeIcon bounce className='text-6xl mr-4 text-[#3ec1c7]' icon={faComment}/>
              <Image src={iscore} alt="iScore" width={200}/>
            </div>
            
            {/* English Content */}
            <>
              <div>
                <p className='font-bold text-white text-6xl'>Get Instant answers</p>
                <p className='font-bold text-white text-6xl'>anytime through iscore's</p>
                <p className='font-bold text-[#3ec1c7] text-6xl italic'>Internal Chatbot</p>
              </div>

              <div>
                <p className='text-gray-300 text-2xl italic'>Provides instant help with HR policies, IT issues, and</p>
                <p className='text-gray-300 text-2xl italic'>company processes - available anytime.</p>
              </div>
              
              <button 
                type='button' 
                className='bg-white rounded-full py-3 font-extrabold w-[60%] text-2xl flex items-center justify-center text-[#4f3795] hover:text-white hover:bg-[#3ec1c7] transition' 
                onClick={goToChatPage}
              >
                I have a question!<FontAwesomeIcon className='pl-6 font-extrabold' fontSize={40} icon={faArrowRight}/>
              </button>
            </>
          </div>
          
          <div className='bg-transparent flex-shrink-0'>
            <Image src={bot} alt="iscore"  width={400}/>
          </div>
        </div>
      )}

    </div>
  );
}
